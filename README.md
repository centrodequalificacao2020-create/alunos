# CQP — Sistema de Gestão Escolar

Sistema web para gestão de escola de idiomas. Desenvolvido com Flask + SQLAlchemy + SQLite.

## Stack

- **Backend:** Python 3.12, Flask 3.0, SQLAlchemy 2.0, Flask-Migrate
- **Banco:** SQLite (arquivo `cqp.db`, gerado automaticamente)
- **PDF:** ReportLab
- **Segurança:** Werkzeug (hash de senha), python-dotenv
- **Servidor:** Gunicorn
- **Hospedagem:** Azure App Service — Brazil South

## Instalação (Windows)

```bash
# 1. Criar e ativar ambiente virtual
py -m venv venv
venv\Scripts\activate

# 2. Instalar dependências
py -m pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
copy .env.example .env
# Edite .env e defina FLASK_SECRET_KEY com um valor aleatório:
# py -c "import os; print(os.urandom(32).hex())"

# 4. Criar banco e usuário admin
py criar_admin.py

# 5. Inicializar migrações (primeira vez)
py -m flask db init
py -m flask db migrate -m "initial"
py -m flask db upgrade

# 6. Rodar o servidor
py app.py
