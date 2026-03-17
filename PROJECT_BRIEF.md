# PROJECT_BRIEF.md
> Leia este arquivo no início de QUALQUER nova thread ou conversa com IA.
> Ele evita re-explicação e garante continuidade entre sessões.

## Projeto
- **Nome:** CQP — Sistema de Gestão Escolar
- **Cliente:** Escola de inglês (proprietário leigo em programação)
- **Repositório:** https://github.com/centrodequalificacao2020-create/alunos
- **URL de produção:** https://cqp-escola-fjb5hhcfe0aaf0a2.brazilsouth-01.azurewebsites.net

## Stack
- **Backend:** Python 3.11 + Flask 3.0.3 + Flask-SQLAlchemy 3.1.1 + Flask-Migrate 4.0.7
- **Banco:** SQLite (`cqp.db`) — futuro: PostgreSQL
- **PDF:** ReportLab 4.2.2
- **Auth:** Werkzeug hash de senha + decorators em `security.py`
- **Servidor:** Gunicorn 22.0.0
- **Hospedagem:** Azure App Service — Brazil South

## Arquitetura
- `app.py` — factory pattern `create_app()`
- `db.py` — SQLAlchemy init, WAL mode, `get_db()`
- `security.py` — hash senha, `@login_required`, `@admin_required`, `@aluno_login_required`
- `config.py` — `SECRET_KEY` via `.env`, sem hardcode
- `models.py` — todos os modelos ORM
- `routes/` — 10 blueprints: `auth`, `aluno`, `cursos`, `financeiro`, `dashboard`, `despesas`, `funcionario`, `conteudos`, `academico`, `portal_aluno`
- `services/` — lógica de negócio separada das rotas
- `templates/` — Jinja2, base.html + subpasta `aluno/` (portal do aluno)
- `migrations/` — Flask-Migrate + Alembic
- `scripts/` — utilitários (ver tabelas, matrículas etc.)

## Módulos do sistema
Alunos, Matrículas, Mensalidades, Frequência, Notas, Conteúdos,
Funcionários, Dashboard, Relatórios financeiros (PDF), Portal do Aluno

## Histórico de refatoração
| Commit | O que foi feito |
|---|---|
| Commits 1-2 | Separação em blueprints, `security.py`, `db.py`, hash de senha, `.env` |
| Commit 3 | `portal_aluno.py` corrigido (`alunos/` → `aluno/`), scripts movidos para `scripts/` |
| Commit 4 (135cd99) | Dashboard, relatórios, templates refatorados, `models.py` corrigido |
| 9f38547 | `startup.sh` adicionado para Azure factory pattern |
| a1b51d6 | `.github/workflows/azure-deploy.yml` adicionado |

## Pendências abertas
- [ ] Cadastrar `AZURE_WEBAPP_PUBLISH_PROFILE` nos secrets do GitHub (fazer com o cliente em 18/03)
- [ ] Executar `git rm --cached -r venv/` localmente para remover venv do git
- [ ] Rodar `flask db upgrade` após primeiro deploy no Azure
- [ ] Rodar `criar_admin.py` no servidor após deploy
- [ ] Testes com o cliente (19/03)

## Regras inegociáveis de código
- **NUNCA** usar `sqlite3` direto — sempre SQLAlchemy via `db.py`
- **SEMPRE** `@login_required` em rotas que alteram dados
- **NUNCA** hardcode de senhas ou chaves — sempre via `.env`
- Blueprints para novos módulos — nunca adicionar rotas no `app.py`
- Docstring em toda função nova

## Prazo
**20/03/2026 às 17h (Brasília)** — sistema funcionando em produção para o cliente
