"""
routes/admin_utils.py
=====================
Rotas utilitarias para administradores.

Rota: GET/POST /admin/resetar-senhas-alunos
  - Define senha = CPF (sem mascara) para alunos SEM hash valido.
  - Exige que o admin digite a palavra CONFIRMAR antes de executar.
  - Alunos que ja possuem hash valido NAO sao alterados.
"""
import re
from flask import Blueprint, render_template_string, redirect, flash, session, request
from db import db
from models import Aluno
from security import admin_required, hash_senha

admin_utils_bp = Blueprint("admin_utils", __name__)


def _cpf_limpo(cpf):
    return re.sub(r"\D", "", cpf or "")


def _senha_valida(hash_str):
    """Retorna True se o hash parece um hash werkzeug valido."""
    if not hash_str:
        return False
    return hash_str.startswith(("pbkdf2:", "scrypt:", "sha256$", "$2b$"))


PALAVRA_CONFIRMACAO = "CONFIRMAR"

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
  .erro-conf{background:#fef2f2;border:1px solid #fca5a5;padding:10px;
             border-radius:6px;margin-bottom:12px;color:#b91c1c;font-size:13px}
  .confirm-box{margin:16px 0;padding:14px;background:#f0fdf4;
               border:1px solid #86efac;border-radius:6px}
  .confirm-box label{font-weight:bold;font-size:13px}
  .confirm-box input[type=text]{margin-top:6px;padding:8px 12px;
    border:1px solid #d1d5db;border-radius:4px;font-size:14px;width:200px}
</style></head><body>
<h1>🔑 Resetar Senhas dos Alunos</h1>
<div class='aviso'>
  <strong>O que esta ferramenta faz:</strong> define a senha de cada aluno
  que <em>ainda nao tem hash valido</em> para o <strong>CPF sem pontos e traco</strong>.
  Alunos que ja possuem senha valida <strong>nao sao alterados</strong>.<br><br>
  <strong>⚠️ Operação irreversível.</strong> Pense antes de executar.
</div>
{% if erro_confirmacao %}
  <div class='erro-conf'>❌ {{ erro_confirmacao }}</div>
{% endif %}
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
  <p>Digite <strong>CONFIRMAR</strong> no campo abaixo e clique no botao para redefinir
  as senhas de todos os alunos sem hash valido.</p>
  <form method='POST'>
    <input type='hidden' name='csrf_token' value='{{ csrf_token() }}'>
    <div class='confirm-box'>
      <label for='confirmacao'>Palavra de confirmação:</label><br>
      <input type='text' id='confirmacao' name='confirmacao'
             placeholder='Digite CONFIRMAR' autocomplete='off'>
    </div>
    <button type='submit' class='btn'>🔄 Executar Reset de Senhas</button>
    <a href='/cadastro' class='btn' style='background:#6b7280;margin-left:8px'>Cancelar</a>
  </form>
{% endif %}
</body></html>
"""


@admin_utils_bp.route("/admin/resetar-senhas-alunos", methods=["GET", "POST"])
@admin_required
def resetar_senhas_alunos():
    resultado        = None
    atualizados      = 0
    total            = 0
    erro_confirmacao = None

    if request.method == "POST":
        confirmacao = (request.form.get("confirmacao") or "").strip()

        # Bug 4 fix: exige digitação explícita da palavra CONFIRMAR
        if confirmacao != PALAVRA_CONFIRMACAO:
            erro_confirmacao = (
                f"Você digitou \u201c{confirmacao}\u201d. "
                f"Digite exatamente \u201c{PALAVRA_CONFIRMACAO}\u201d para prosseguir."
            )
        else:
            alunos    = Aluno.query.order_by(Aluno.nome).all()
            total     = len(alunos)
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

    return render_template_string(
        PAGE,
        resultado        = resultado,
        atualizados      = atualizados,
        total            = total,
        erro_confirmacao = erro_confirmacao,
    )
