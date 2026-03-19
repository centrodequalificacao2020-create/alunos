# PROJECT_BRIEF.md
> Leia este arquivo **no início de QUALQUER nova thread ou conversa com IA**.
> Ele evita re-explicação e garante continuidade entre sessões.

## Projeto
- **Nome:** CQP — Sistema de Gestão Escolar
- **Cliente:** Escola de inglês (proprietário leigo em programação)
- **Repositório:** https://github.com/centrodequalificacao2020-create/alunos
- **URL de produção:** https://cqp-escola-fjb5hhcfe0aaf0a2.brazilsouth-01.azurewebsites.net

## Stack
- **Backend:** Python 3.12 + Flask 3.0 + Flask-SQLAlchemy 2.0 + Flask-Migrate
- **Banco:** SQLite (`cqp.db`) — futuro: PostgreSQL
- **PDF:** ReportLab
- **Extras:** python-dateutil (`relativedelta` para cálculo de parcelas)
- **Auth:** Werkzeug hash de senha + decorators em `security.py`
- **Servidor:** Gunicorn via `startup.sh`
- **Hospedagem:** Azure App Service — Brazil South
- **CI/CD:** `.github/workflows/azure-deploy.yml`

## Arquitetura
- `app.py` — `create_app()` factory; registra 10 blueprints; cria `uploads/`
- `db.py` — SQLAlchemy init, WAL mode, `engine.connect()` + `text()`
- `security.py` — `hash_senha`, `verificar_senha`, `@login_required`, `@admin_required`, `@aluno_login_required`, `extensao_permitida`
- `config.py` — `SECRET_KEY` e `UPLOAD_FOLDER` via `.env`; `MAX_CONTENT_LENGTH = 10 MB`
- `models.py` — 15 modelos ORM; `Materia` tem `conteudos = relationship(backref="materia")`; `Conteudo` tem campo `video`
- `routes/` — 10 blueprints (ver tabela abaixo)
- `services/matricula_service.py` — `criar_matricula(form)`: cria `Matricula` + `Mensalidade` (taxa, parcelas mensais, material) numa única transação com rollback
- `services/pdf_service.py` — `gerar_recibo`, `gerar_carne`, `gerar_boletim_notas`, `gerar_historico_frequencia`
- `templates/` — Jinja2; `base.html` + subpasta `aluno/` (portal do aluno)
- `migrations/` — Flask-Migrate + Alembic
- `scripts/` — utilitários de diagnóstico/manutenção do banco (NÃO usar em produção diretamente)

## Blueprints e rotas principais

| Blueprint | Arquivo | Rotas principais |
|---|---|---|
| `auth_bp` | `routes/auth.py` | `GET/POST /login`, `GET /logout`, `GET /` |
| `aluno_bp` | `routes/aluno.py` | `GET/POST /cadastro`, `/editar_aluno/<id>`, `/excluir_aluno/<id>`, `/aluno/<id>` |
| `cursos_bp` | `routes/cursos.py` | `GET /cursos`, `/salvar_curso`, `/editar_curso/<id>`, `/excluir_curso/<id>` |
| `financeiro_bp` | `routes/financeiro.py` | `GET /financeiro`, `/pagar/<id>`, `/editar_parcela/<id>`, `/excluir_parcela/<id>/<aluno_id>`, `/recibo/<id>`, `/carne/<aluno_id>`, `/movimentacao`, `/salvar_matricula` |
| `dashboard_bp` | `routes/dashboard.py` | `GET /dashboard`, `/salvar_relatorio`, `/carregar_relatorio/<mes>`, `/relatorio_trimestre/<ano>/<tri>` |
| `despesas_bp` | `routes/despesas.py` | `GET/POST /despesas`, `/editar_despesa/<id>`, `/excluir_despesa/<id>` |
| `funcionario_bp` | `routes/funcionario.py` | `GET /funcionarios`, `/salvar_funcionario`, `/editar_funcionario/<id>`, `/excluir_funcionario/<id>`, `/ver_funcionario/<id>` |
| `conteudos_bp` | `routes/conteudos.py` | `GET/POST /conteudos`, `/conteudos/excluir/<id>` |
| `academico_bp` | `routes/academico.py` | `/turmas`, `/materias`, `/notas`, `/frequencia`, `/frequencia_historico`, PDFs, `/backup` |
| `portal_aluno_bp` | `routes/portal_aluno.py` | `/aluno/login`, `/aluno/logout`, `/aluno/dashboard`, `/aluno/frequencia`, `/aluno/conteudo`, `/aluno/concluir/<id>` |

## Modelos críticos

**Matricula** — campos: `aluno_id`, `curso_id`, `tipo_curso`, `data_matricula`, `status` (`"ATIVA"`), `valor_matricula`, `valor_mensalidade`, `quantidade_parcelas`, `material_didatico`, `valor_material`, `observacao`

**Mensalidade** — campos: `aluno_id`, `valor`, `vencimento`, `status` (`"Pendente"/"Pago"`), `tipo` (`"Mensalidade"/"Matrícula"/"Material"`), `parcela_ref`, `data_pagamento`, `forma_pagamento`, `usuario_pagamento`; índices em `aluno_id`, `vencimento`, `status`

**Aluno** — `status` pode ser `"Ativo"`, `"Pré-Matrícula"`, `"Cancelado"`; campo `senha` para acesso ao portal do aluno

**Conteudo** — campos: `materia_id`, `titulo`, `descricao`, `arquivo`, `video` (URL externa); `video` tem prioridade sobre `arquivo` no template `aluno/conteudo.html`

## CSS / Frontend

- **`static/style.css`** — arquivo único; 27 seções documentadas com comentários `/* ── N. NOME ── */`
- **`.card`** tem `overflow-x: hidden` — **atenção:** isso corta listas de autocomplete absolutas; cards com autocomplete precisam de `overflow: visible`
- **`.autocomplete-lista`** — `position: absolute`, `z-index: 999`, `max-height: 220px`, `overflow-y: auto`; fechar ao clicar fora já implementado via `document.addEventListener('click', ...)`
- **JS por página** — cada template tem seu próprio `<script>` inline ou em `static/js/<pagina>.js`

## Histórico de commits relevantes

| Commit | O que foi feito |
|---|---|
| Commits 1–2 | Separação em blueprints, `security.py`, `db.py`, hash de senha, `.env` |
| Commit 3 | `portal_aluno.py` corrigido (`alunos/` → `aluno/`), scripts movidos para `scripts/` |
| 135cd99 | `models.py` corrigido: `Materia.conteudos` relationship + campo `video` em `Conteudo` |
| 59f7739 | Commit 4 — templates refatorados: `dashboard.html`, `relatorio.html`, `conteudos.html`, `ficha_aluno.html`, `boletim`, `cursos`, `materias`, `notas`, `ver_funcionario`, `aluno/conteudo.html` |
| 9f38547 | `startup.sh` adicionado para Azure factory pattern |
| a1b51d6 | `.github/workflows/azure-deploy.yml` adicionado |
| Sessão 18/03 | Migration `turmas`, `turma_alunos`, `notas` aplicada |

## Pendências abertas (19/03/2026)

- [ ] **CRÍTICO:** Cadastrar `AZURE_WEBAPP_PUBLISH_PROFILE` nos secrets do GitHub (fazer com o cliente presencialmente)
- [ ] **BUG:** `overflow-x: hidden` no `.card` corta lista de autocomplete na página `/financeiro` — remover ou substituir por `overflow: visible` no card que contém o `#fin-wrap`
- [ ] **BUG:** Paginação na listagem de alunos (`GET /cadastro`) — `Aluno.query.order_by().all()` retorna todos sem limite; implementar `paginate(page, per_page=20)`
- [ ] **BUG:** Validação de dupla matrícula ativa — `criar_matricula()` em `matricula_service.py` não verifica se já existe `Matricula` com `aluno_id` + `curso_id` + `status="ATIVA"`; adicionar guard antes do `db.session.add(matricula)`
- [ ] **LOCAL:** Executar `git rm --cached -r venv/` + commit + push (venv ainda rastreada no git — não pode ser feito via API)
- [ ] Rodar `flask db migrate -m "add video to conteudos"` + `flask db upgrade` no servidor (coluna `video` adicionada ao modelo mas pode não existir no banco de produção)
- [ ] Rodar `flask db upgrade` no Azure após primeiro deploy
- [ ] Rodar `criar_admin.py` no servidor após deploy
- [ ] Testes com o cliente — **19/03/2026 às 17h**

## Regras inegociáveis de código
- **NUNCA** usar `sqlite3` direto — sempre SQLAlchemy via `db.py`
  - **Exceção documentada:** `academico.py /backup` usa `sqlite3.backup()` propositalmente para cópia consistente do banco — não alterar
- **SEMPRE** `@login_required` em rotas que alteram dados
- **NUNCA** hardcode de senhas ou chaves — sempre via `.env`
- Blueprints para novos módulos — nunca adicionar rotas em `app.py`
- Paginação obrigatória em listagens com potencial de crescimento
- CSS sempre em `static/style.css` — nunca `style=""` inline nos templates

## Prazo
**19/03/2026 às 17h (Brasília)** — sistema funcionando em produção para o cliente
