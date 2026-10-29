#!/usr/bin/env python3
"""Conferência (somente leitura) das taxas de matrícula.

Verifica dois problemas no banco em produção:

1. TAXAS DUPLICADAS — o mesmo aluno com 2+ taxas de matrícula pagas no
   mesmo curso. Normalmente é uma mensalidade lançada com `tipo='matricula'`
   por engano.

2. TAXAS AUSENTES — alunos com matrícula ATIVA que não têm nenhuma taxa de
   matrícula lançada (por isso não aparecem no card "Matrículas novas").

NÃO altera nada no banco: apenas SELECTs.

Uso (PythonAnywhere, dentro do virtualenv do projeto):

    cd ~/alunos
    workon <nome-do-virtualenv>
    python scripts/conferir_taxas_matricula.py

Opções:
    --desde 2026-01-01   período inicial considerado (default: 2026-01-01)
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from db import db  # noqa: E402
from models import Aluno, Curso, Matricula, Mensalidade  # noqa: E402
from sqlalchemy import func  # noqa: E402


def _brl(valor) -> str:
    try:
        return f"R$ {float(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "-"


def _cabecalho(titulo: str) -> None:
    print()
    print("=" * 78)
    print(titulo)
    print("=" * 78)


def taxas_duplicadas(desde: str):
    """Aluno + curso com 2 ou mais taxas de matrícula pagas."""
    linhas = (
        db.session.query(Mensalidade)
        .filter(
            func.lower(Mensalidade.tipo) == "matricula",
            Mensalidade.status == "Pago",
            Mensalidade.data_pagamento >= desde,
        )
        .order_by(Mensalidade.aluno_id, Mensalidade.curso_id, Mensalidade.data_pagamento)
        .all()
    )

    grupos = defaultdict(list)
    for m in linhas:
        grupos[(m.aluno_id, m.curso_id)].append(m)

    duplicados = {k: v for k, v in grupos.items() if len(v) > 1}
    return duplicados


def taxas_ausentes(desde: str):
    """Matrículas ATIVAS sem nenhuma taxa de matrícula lançada."""
    matriculas = (
        db.session.query(Matricula)
        .filter(
            func.upper(Matricula.status) == "ATIVA",
            Matricula.data_matricula >= desde,
        )
        .order_by(Matricula.data_matricula.desc())
        .all()
    )

    sem_taxa = []
    for mat in matriculas:
        tem_taxa = (
            db.session.query(Mensalidade.id)
            .filter(
                Mensalidade.aluno_id == mat.aluno_id,
                func.lower(Mensalidade.tipo) == "matricula",
                db.or_(
                    Mensalidade.curso_id == mat.curso_id,
                    Mensalidade.curso_id.is_(None),
                ),
            )
            .first()
        )
        if not tem_taxa:
            sem_taxa.append(mat)
    return sem_taxa


def main() -> int:
    parser = argparse.ArgumentParser(description="Confere taxas de matrícula (somente leitura).")
    parser.add_argument("--desde", default="2026-01-01", help="Data inicial (YYYY-MM-DD).")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        # Mostra de onde os dados estão vindo (não expõe credenciais).
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if uri.startswith("sqlite"):
            caminho = uri.split("///")[-1]
            print(f"Banco: SQLite -> {caminho}")
            if os.path.exists(caminho):
                mtime = datetime.fromtimestamp(os.path.getmtime(caminho))
                print(f"Modificado em: {mtime:%d/%m/%Y %H:%M}")
        else:
            print("Banco: externo (DATABASE_URL configurada)")

        total_linhas = Mensalidade.query.count()
        ultimo_pag = (
            db.session.query(func.max(Mensalidade.data_pagamento))
            .filter(Mensalidade.status == "Pago")
            .scalar()
        )
        print(f"Mensalidades: {total_linhas} | último pagamento registrado: {ultimo_pag}")
        print(f"Período analisado: a partir de {args.desde}")

        # ── 1. Duplicidades ────────────────────────────────────────────────
        duplicados = taxas_duplicadas(args.desde)
        _cabecalho(f"1) TAXAS DE MATRÍCULA DUPLICADAS: {len(duplicados)} caso(s)")

        if not duplicados:
            print("Nenhuma duplicidade encontrada.")
        else:
            cursos = {c.id: c.nome for c in Curso.query.all()}
            alunos = {a.id: a for a in Aluno.query.all()}

            for (aluno_id, curso_id), mens in sorted(duplicados.items()):
                aluno = alunos.get(aluno_id)
                curso = cursos.get(curso_id, "—")
                print()
                print(f"Aluno #{aluno_id} — {aluno.nome if aluno else '?'}")
                print(f"  Curso: {curso} (id {curso_id})")
                print(f"  {'mens_id':>8} {'valor':>12} {'vencimento':>12} "
                      f"{'pagamento':>12} {'parcela':>8}  registrado por")
                for m in mens:
                    print(f"  {m.id:>8} {_brl(m.valor):>12} {str(m.vencimento):>12} "
                          f"{str(m.data_pagamento):>12} {str(m.parcela_ref or '-'):>8}  "
                          f"{m.usuario_pagamento or '-'}")

                # Sugere qual linha provavelmente está com o tipo errado:
                # a taxa deveria vencer junto com a matrícula, não meses depois.
                primeira = mens[0].vencimento or ""
                suspeitas = [m for m in mens[1:] if (m.vencimento or "")[:7] != primeira[:7]]
                for m in suspeitas:
                    print(f"  -> Suspeita: mensalidade #{m.id} (vence {m.vencimento}) "
                          f"lançada como tipo 'matricula'.")

        # ── 2. Taxas ausentes ──────────────────────────────────────────────
        ausentes = taxas_ausentes(args.desde)
        _cabecalho(f"2) MATRÍCULAS ATIVAS SEM TAXA LANÇADA: {len(ausentes)}")

        if not ausentes:
            print("Todas as matrículas ativas têm taxa lançada.")
        else:
            cursos = {c.id: c.nome for c in Curso.query.all()}
            alunos = {a.id: a for a in Aluno.query.all()}
            print(f"{'matricula':>10} {'aluno_id':>9} {'nome':<34} {'data':>11}  curso")
            for mat in ausentes[:10]:
                aluno = alunos.get(mat.aluno_id)
                print(f"{mat.id:>10} {mat.aluno_id:>9} "
                      f"{(aluno.nome if aluno else '?')[:34]:<34} "
                      f"{str(mat.data_matricula):>11}  {cursos.get(mat.curso_id, '—')}")
            if len(ausentes) > 10:
                print(f"... e mais {len(ausentes) - 10} matrícula(s).")
            print()
            print("Nota: matrículas antigas (importadas) podem não ter taxa lançada.")
            print("      Isso não afeta o card, que agora conta pela taxa paga.")

        # ── 3. Resumo card × lista ─────────────────────────────────────────
        _cabecalho("3) RESUMO: taxa paga por mês (base do card e das listas)")
        resumo = (
            db.session.query(
                func.substr(Mensalidade.data_pagamento, 1, 7).label("mes"),
                func.count().label("linhas"),
                func.count(func.distinct(Mensalidade.aluno_id)).label("alunos"),
                func.sum(Mensalidade.valor).label("total"),
            )
            .filter(
                func.lower(Mensalidade.tipo) == "matricula",
                Mensalidade.status == "Pago",
                Mensalidade.data_pagamento >= args.desde,
            )
            .group_by("mes")
            .order_by(db.desc("mes"))
            .all()
        )
        print(f"{'mês':>9} {'linhas':>7} {'alunos':>7} {'valor':>14}  obs")
        for mes, linhas, alunos_qtd, total in resumo:
            obs = ""
            if linhas > alunos_qtd:
                obs = "há aluno com 2+ taxas no mês (deduplicado no card)"
            print(f"{mes:>9} {linhas:>7} {alunos_qtd:>7} {_brl(total):>14}  {obs}")

        print()
        print("Concluído. Nenhum dado foi alterado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
