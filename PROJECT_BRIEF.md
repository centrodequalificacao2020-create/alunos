# PROJECT_BRIEF.md
> Leia este arquivo **no início de QUALQUER nova thread ou conversa com IA**.
> Ele evita re-explicação e garante continuidade entre sessões.

## Projeto
- **Nome:** CQP — Sistema de Gestão Escolar
- **Cliente:** Escola de inglês (proprietário leigo em programação)
- **Repositório:** https://github.com/centrodequalificacao2020-create/alunos
- **URL de produção:** https://centrodequalificacao2020-create.pythonanywhere.com

## Stack
- **Backend:** Python 3.12 + Flask 3.0 + Flask-SQLAlchemy 2.0 + Flask-Migrate
- **Banco:** SQLite (`cqp.db`) — futuro: PostgreSQL
- **PDF:** ReportLab
- **Extras:** python-dateutil (`relativedelta` para cálculo de parcelas)
- **Auth:** Werkzeug hash de senha + decorators em `security.py`
- **Hospedagem:** PythonAnywhere (substituiu Azure em mar/2026)
- **Deploy:** `git pull` na pasta do projeto + `touch /var/www/<wsgi_file>.py` para recarregar

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
| `despesas_bp` | `routes/despesas.py` | `GET /despesas`, `/editar_despesa/<id>`, `/excluir_despesa/<id>` |
| `funcionario_bp` | `routes/funcionario.py` | `GET /funcionarios`, `/salvar_funcionario`, `/editar_funcionario/<id>`, `/excluir_funcionario/<id>`, `/ver_funcionario/<id>` |
| `conteudos_bp` | `routes/conteudos.py` | `GET/POST /conteudos`, `/conteudos/excluir/<id>` |
| `academico_bp` | `routes/academico.py` | `/turmas`, `/materias`, `/notas`, `/frequencia`, `/frequencia_historico`, PDFs, `/backup` |
| `portal_aluno_bp` | `routes/portal_aluno.py` | `/aluno/login`, `/aluno/logout`, `/aluno/dashboard`, `/aluno/financeiro`, `/aluno/notas`, `/aluno/frequencia`, `/aluno/conteudo`, `/aluno/concluir/<id>`, `/aluno/arquivo/<id>`, `/aluno/senha` |

## Modelos críticos

**Matricula** — campos: `aluno_id`, `curso_id`, `tipo_curso`, `data_matricula`, `status` (`"ATIVA"`), `valor_matricula`, `valor_mensalidade`, `quantidade_parcelas`, `material_didatico`, `valor_material`, `observacao`

**Mensalidade** — campos: `aluno_id`, `valor`, `vencimento`, `status` (`"Pendente"/"Pago"`), `tipo` (`"Mensalidade"/"Matrícula"/"Material"`), `parcela_ref`, `data_pagamento`, `forma_pagamento`, `usuario_pagamento`; índices em `aluno_id`, `vencimento`, `status`

**Aluno** — `status` pode ser `"Ativo"`, `"Pré-Matrícula"`, `"Cancelado"`; campo `senha` para acesso ao portal do aluno

**Conteudo** — campos: `materia_id`, `titulo`, `descricao`, `arquivo`, `video` (URL externa); `video` tem prioridade sobre `arquivo` no template `aluno/conteudo.html`

## CSS / Frontend

- **`static/style.css`** — arquivo único; 32 seções documentadas com comentários `/* ── N. NOME ── */`
- A **seção 32** (`body.tema-aluno`) é o tema escuro do portal do aluno — isolada, não afeta páginas admin
- **`.card`** padrão tem `overflow-x: visible` (corrigido em v7+)
- **`.autocomplete-lista`** — `position: absolute`, `z-index: 999`, `max-height: 220px`, `overflow-y: auto`
- **JS por página** — cada template tem seu próprio `<script>` inline

## Portal do Aluno — Tema Escuro (`body.tema-aluno`)

### Como funciona
- `templates/base.html` adiciona a classe `tema-aluno` ao `<body>` automaticamente para qualquer rota `/aluno/*`
- Fundo: `linear-gradient(135deg, #0f2027, #203a43, #2c5364)`
- Header glass: `rgba(13,33,59,0.88)` + `backdrop-filter: blur(10px)`
- Cards glass escuro: `background: rgba(15,32,55,0.82)`, borda `rgba(255,255,255,.12)`

### Templates do portal do aluno
| Template | Descrição |
|---|---|
| `templates/aluno/dashboard.html` | Tela inicial — boas-vindas + cards de navegação com ícones FA |
| `templates/aluno/financeiro.html` | Extrato de parcelas do aluno |
| `templates/aluno/notas.html` | Boletim de notas |
| `templates/aluno/frequencia.html` | Frequência por matéria |
| `templates/aluno/conteudo.html` | Player de aulas (PDF.js + iframe YouTube/Vimeo) com sidebar de navegação |
| `templates/aluno/senha.html` | Troca de senha |
| `templates/aluno/login.html` | Login do aluno |

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
| Sessão 25/03 | Migração Azure → PythonAnywhere; `style.css` v8: seção 32 tema-aluno; `aluno/dashboard.html` reescrito com visual dark; `base.html` com classe `tema-aluno` automática |
| 6b9ff29 | `style.css` v8 — seção 32 tema-aluno com cards glass, tabelas e inputs adaptados |

## Pendências abertas (25/03/2026)

### BUGS — Portal do Aluno (tema escuro)
- [ ] **`body.tema-aluno main`** está com `padding: 0` → cards colam no header. **Fix:** `body.tema-aluno main { padding: 24px 32px; }`
- [ ] **Sidebar branca** em `aluno/conteudo.html` — `.sidebar` usa `background: var(--color-surface)` (branco). **Fix:**
  ```css
  body.tema-aluno .sidebar {
      background: rgba(15, 32, 55, 0.82);
      border: 1px solid rgba(255,255,255,.12);
      color: #f0f4f8;
  }
  body.tema-aluno .materia-titulo { color: rgba(180,210,240,0.7); }
  body.tema-aluno .aula { color: #dce8f5; border-bottom-color: rgba(255,255,255,.08); }
  body.tema-aluno .aula:hover { background: rgba(0,198,255,.10); }
  body.tema-aluno .aula.ativa  { background: rgba(0,198,255,.22); }
  body.tema-aluno .progresso-barra { background: rgba(255,255,255,.15); }
  ```
- [ ] **Cards brancos em outras páginas do portal** (`/aluno/financeiro`, `/aluno/notas`, etc.) — o override `body.tema-aluno .card` pode não estar cobrindo todos os casos; verificar se há `!important` ou especificidade maior nos templates inline
- [ ] **Textos ilegíveis fora de `.card`** — textos gerais diretamente no `main` (fora de cards) ficam com cor dark padrão sobre fundo escuro; adicionar `body.tema-aluno { color: #f0f4f8; }`

### Pendências gerais
- [ ] **BUG:** Paginação na listagem de alunos (`GET /cadastro`) — `Aluno.query.order_by().all()` retorna todos sem limite
- [ ] **BUG:** Validação de dupla matrícula ativa — `criar_matricula()` não verifica `Matricula` com `aluno_id + curso_id + status="ATIVA"` já existente
- [ ] Rodar `flask db migrate` + `flask db upgrade` no PythonAnywhere se houver colunas novas
- [ ] Executar `criar_admin.py` no servidor se necessário

## Regras inegociáveis de código
- **NUNCA** usar `sqlite3` direto — sempre SQLAlchemy via `db.py`
  - **Exceção documentada:** `academico.py /backup` usa `sqlite3.backup()` propositalmente — não alterar
- **SEMPRE** `@login_required` / `@aluno_login_required` em rotas que alteram dados
- **NUNCA** hardcode de senhas ou chaves — sempre via `.env`
- Blueprints para novos módulos — nunca adicionar rotas em `app.py`
- Paginação obrigatória em listagens com potencial de crescimento
- **CSS sempre em `static/style.css`** — nunca `style=""` inline nos templates
- Alterações no tema do portal do aluno: **sempre dentro de `body.tema-aluno { ... }`** na seção 32 do CSS
