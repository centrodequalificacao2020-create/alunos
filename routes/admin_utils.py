"""
routes/admin_utils.py
=====================
Rotas utilitarias para administradores.
Atualmente:
  GET/POST /admin/resetar-senhas-alunos
    — redefine a senha de TODOS os alunos que nao possuem hash valido,
      usando o CPF sem mascara como senha padrao.
      Se o aluno nao tiver CPF, usa o ID numerado (ex: 'aluno42').
"""
import re
from flask import Blueprint, render_template_string, redirect, flash, session
from db import db
from models import Aluno
from security import admin_required, hash_senha, verificar_senha

admin_utils_bp = Blueprint("admin_utils", __name__)


def _cpf_limpo(cpf):
    return re.sub(r"\D", "", cpf or "")


def _senha_valida(hash_str):
    """Retorna True se o hash parece um hash werkzeug valido."""
    if not hash_str:
        return False
    return hash_str.startswith(("pbkdf2:", "scrypt:", "sha256$", "$2b$"))


PAGE = """
<!doctype html><html lang='pt-br'><head>
<meta charset='UTF-8'>
<title>Resetar Senhas</title>
<style>
  body{font-family:sans-serif;max-width:700px;margin:40px auto;padding:0 20px}
  h1{color:#1a56db} table{width:100%;border-collapse:collapse;margin-top:20px}
  th,td{border:1px solid #ddd;padding:8px 12px;font-size:13px}
  th{background:#f3f4f6} tr:nth-child(even){background:#f9fafb}
  .ok{color:#15803d;font-weight:bold} .skip{color:#9ca3af}
  .btn{display:inline-block;margin-top:20px;padding:10px 22px;
       background:#1a56db;color:#fff;border:none;border-radius:6px;
       cursor:pointer;font-size:14px;text-decoration:none}
  .btn-verde{background:#15803d}
  .aviso{background:#fefce8;border:1px solid #fde047;padding:12px;
          border-radius:6px;margin-bottom:16px;font-size:13px}
</style></head><body>
<h1>🔑 Resetar Senhas dos Alunos</h1>
<div class='aviso'>
  <strong>O que esta ferramenta faz:</strong> define a senha de cada aluno
  que <em>ainda nao tem hash valido</em> para o <strong>CPF sem pontos e traco</strong>.
  Alunos que ja possuem senha valida <strong>nao sao alterados</strong>.
</div>
{% if resultado %}
  <p><strong>{{ atualizados }} aluno(s) atualizados</strong> de {{ total }} no banco.</p>
  <table>
    <thead><tr><th>#</th><th>Nome</th><th>CPF</th><th>Senha definida como</th><th>Status</th></tr></thead>
    <tbody>
    {% for r in resultado %}
      <tr>
        <td>{{ r.id }}</td>
        <td>{{ r.nome }}</td>
        <td>{{ r.cpf }}</td>
        <td><code>{{ r.nova_senha }}</code></td>
        <td class='{{ "ok" if r.ok else "skip" }}'>{{ "✔ atualizado" if r.ok else "— ja tinha senha" }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  <a href='/cadastro' class='btn btn-verde' style='margin-right:10px'>← Voltar para Alunos</a>
{% else %}
  <p>Clique no botao abaixo para redefinir as senhas de todos os alunos sem hash valido.</p>
  <form method='POST'>
    <input type='hidden' name='csrf_token' value='{{ csrf_token() }}'>
    <button type='submit' class='btn'>🔄 Executar Reset de Senhas</button>
    <a href='/cadastro' class='btn' style='background:#6b7280;margin-left:8px'>Cancelar</a>
  </form>
{% endif %}
</body></html>
"""


@admin_utils_bp.route("/admin/resetar-senhas-alunos", methods=["GET", "POST"])
@admin_required
def resetar_senhas_alunos():
    from flask import request
    resultado   = None
    atualizados = 0
    total       = 0

    if request.method == "POST":
        alunos  = Aluno.query.order_by(Aluno.nome).all()
        total   = len(alunos)
        resultado = []

        for a in alunos:
            ja_tem = _senha_valida(a.senha)
            cpf    = _cpf_limpo(a.cpf)
            nova   = cpf if cpf else f"aluno{a.id}"

            if not ja_tem:
                a.senha = hash_senha(nova)
                atualizados += 1
                resultado.append(dict(id=a.id, nome=a.nome, cpf=a.cpf or "",
                                      nova_senha=nova, ok=True))
            else:
                resultado.append(dict(id=a.id, nome=a.nome, cpf=a.cpf or "",
                                      nova_senha="(mantida)", ok=False))

        db.session.commit()

    from flask import render_template_string
    return render_template_string(
        PAGE,
        resultado=resultado,
        atualizados=atualizados,
        total=total,
    )
