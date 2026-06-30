"""migrar_uploads_cloudinary.py

Migra arquivos legados (salvos localmente em static/uploads/) para o Cloudinary.
Atualiza os campos `arquivo` e `arquivo_public_id` nos modelos Conteudo e Exercicio.

Uso (console PythonAnywhere):
    cd ~/alunos
    python scripts/migrar_uploads_cloudinary.py

O script é seguro para rodar mais de uma vez (idempotente):
    - Ignora registros cujo `arquivo` já começa com http (já estão no Cloudinary).
    - Ignora registros sem arquivo.
    - Em caso de erro num registro, continua com o próximo.

Depois de confirmar que tudo subiu, apague os arquivos locais:
    rm -rf ~/alunos/static/uploads/*
"""

import os
import sys

# Garante que o diretório raiz do projeto está no path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from app import create_app
from db import db
from models import Conteudo, Exercicio
from services.storage_service import upload_arquivo

UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads")


def migrar_modelo(app, Modelo, pasta_cloudinary):
    migrados = 0
    ignorados = 0
    erros = []

    with app.app_context():
        registros = Modelo.query.filter(
            Modelo.arquivo.isnot(None),
            ~Modelo.arquivo.like("http%"),  # só arquivos locais
        ).all()

        print(f"\n[{Modelo.__name__}] {len(registros)} registro(s) para migrar...")

        for obj in registros:
            nome_arquivo = os.path.basename(obj.arquivo.strip())
            caminho = os.path.join(UPLOADS_DIR, nome_arquivo)

            if not os.path.isfile(caminho):
                msg = f"  ⚠  id={obj.id} | arquivo não encontrado no disco: {caminho}"
                print(msg)
                erros.append(msg)
                ignorados += 1
                continue

            try:
                with open(caminho, "rb") as f:
                    resultado = upload_arquivo(
                        f,
                        pasta=pasta_cloudinary,
                        nome_publico=nome_arquivo,
                    )

                obj.arquivo = resultado["url"]
                obj.arquivo_public_id = resultado["public_id"]
                db.session.commit()
                migrados += 1
                print(f"  ✓  id={obj.id} | {nome_arquivo} → {resultado['url'][:60]}...")

            except Exception as e:
                db.session.rollback()
                msg = f"  ✗  id={obj.id} | {nome_arquivo} | erro: {e}"
                print(msg)
                erros.append(msg)

    return migrados, ignorados, erros


def main():
    print("=" * 60)
    print("  Migração de uploads legados → Cloudinary")
    print("=" * 60)

    app = create_app()

    total_migrados = 0
    total_ignorados = 0
    todos_erros = []

    for Modelo, pasta in [(Conteudo, "conteudos"), (Exercicio, "exercicios")]:
        m, i, e = migrar_modelo(app, Modelo, pasta)
        total_migrados += m
        total_ignorados += i
        todos_erros.extend(e)

    print("\n" + "=" * 60)
    print(f"  RESULTADO FINAL")
    print(f"  Migrados com sucesso : {total_migrados}")
    print(f"  Arquivos não achados : {total_ignorados}")
    print(f"  Erros de upload      : {len(todos_erros)}")
    print("=" * 60)

    if todos_erros:
        print("\nDetalhes dos erros:")
        for e in todos_erros:
            print(e)
        print("\n⚠  Corrija os erros acima antes de apagar static/uploads/")
    else:
        print("\n✓  Todos os arquivos migrados!")
        print("   Quando confirmar as URLs no sistema, rode:")
        print("   rm -rf ~/alunos/static/uploads/*")


if __name__ == "__main__":
    main()
