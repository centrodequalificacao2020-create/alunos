# CQP — Sistema de Gestão Escolar

Sistema web para gestão de alunos, financeiro e acadêmico.
Desenvolvido com Flask + SQLAlchemy + SQLite.

## Stack

- **Backend:** Python 3.11, Flask 3.0, SQLAlchemy 2.0
- **Banco:** SQLite (arquivo `cqp.db`)
- **PDF:** ReportLab
- **Servidor:** Gunicorn + Nginx
- **Infraestrutura:** Docker + Docker Compose

## Deploy (self-host)

Consulte o arquivo **[INSTALL.md](INSTALL.md)** para o guia completo de instalação
em servidor Ubuntu Server com Docker.

## Desenvolvimento local (Windows)

```bash
# 1. Criar e ativar ambiente virtual
py -m venv venv
venv\Scripts\activate

# 2. Instalar dependências
py -m pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
copy .env.example .env
# Edite .env e defina FLASK_SECRET_KEY:
# py -c "import secrets; print(secrets.token_hex(32))"

# 4. Criar banco e usuário admin
py criar_admin.py

# 5. Rodar o servidor
py app.py
```
