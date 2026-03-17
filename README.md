# CQP — Sistema de Gestão Escolar

Sistema web para gestão de escola de idiomas. Desenvolvido com Flask + SQLAlchemy + SQLite.

## Stack

- **Backend:** Python 3.12, Flask 3.0, SQLAlchemy 2.0, Flask-Migrate
- **Banco:** SQLite (arquivo `cqp.db`, gerado automaticamente)
- **PDF:** ReportLab
- **Segurança:** Werkzeug (hash de senha), python-dotenv

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
```

Acesse: http://localhost:5000 — Login: `admin` / Senha: `admin123`  
> **Troque a senha imediatamente após o primeiro acesso.**

## Estrutura

```
cqp/
├── app.py              # Factory da aplicação Flask
├── config.py           # Configurações via .env
├── db.py               # SQLAlchemy + Flask-Migrate
├── models.py           # Modelos ORM (todas as tabelas)
├── security.py         # Hash de senha, decorators de autenticação
├── logging_config.py   # Configuração de logs rotativos
├── criar_admin.py      # Script de setup inicial do usuário admin
├── routes/             # Blueprints por domínio
│   ├── auth.py
│   ├── aluno.py
│   ├── academico.py
│   ├── financeiro.py
│   ├── dashboard.py
│   ├── despesas.py
│   ├── funcionario.py
│   ├── conteudos.py
│   ├── cursos.py
│   └── portal_aluno.py
├── services/           # Lógica de negócio separada das rotas
├── templates/          # Templates Jinja2
│   └── aluno/          # Portal do aluno
├── static/
│   └── uploads/        # Arquivos enviados pelos usuários
├── scripts/            # Utilitários de manutenção do banco
│   ├── ver_tabelas.py
│   ├── ver_matricula.py
│   ├── ver_conteudos.py
│   ├── ver_frequencias.py
│   ├── inserir_conteudo.py
│   ├── criar_tabela_conteudos.py
│   └── corrigir_conteudos.py
├── migrations/         # Migrações Alembic
├── .env.example        # Modelo de variáveis de ambiente
└── requirements.txt
```

## ⚠️ Remoção do venv/ do rastreamento Git

Se a pasta `venv/` ainda aparecer no repositório, execute **uma única vez** localmente:

```bash
git rm --cached -r venv/
git commit -m "chore: remover venv do rastreamento git"
git push
```

O `.gitignore` já contém `venv/`, então após esse comando ela nunca mais será rastreada.

## Scripts utilitários

Todos os scripts de manutenção ficam em `scripts/` e devem ser executados **da raiz do projeto**:

```bash
py scripts/ver_tabelas.py       # lista tabelas do banco
py scripts/ver_matricula.py     # lista matrículas
py scripts/ver_conteudos.py     # lista conteúdos
py scripts/ver_frequencias.py   # exibe schema de frequencias
```

## Segurança (antes de ir para produção)

- [ ] Definir `FLASK_SECRET_KEY` no `.env` (nunca usar o padrão)
- [ ] Trocar senha do admin após primeiro login
- [ ] Configurar HTTPS (Nginx + Certbot)
- [ ] Habilitar backup automático do `cqp.db`
- [ ] Revisar permissões de perfil por rota
