# RELATÓRIO FINAL CONSOLIDADO v2.6 — Sistema CQP "alunos"
**Auditoria Técnica · Revisão Abril 2026**

> Contexto real incorporado: PythonAnywhere + SQLite + SQLAlchemy (sem Docker em produção)

```
╔══════════════════════════════════════════════════════════════════════╗
║  COMO USAR ESTE DOCUMENTO                                           ║
║  Cole este arquivo inteiro no início de QUALQUER sessão de IA       ║
║  antes de pedir qualquer correção. Ele substitui o PROJECT_BRIEF.md ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## HISTÓRICO DE VERSÕES

| Versão | Data | Alteração |
|---|---|---|
| v2.0 | 05/04/2026 | Relatório consolidado inicial (Sessões S2–S6) |
| v2.1 | 05/04/2026 | **Fase 1 concluída** — BUG-01 a BUG-06 marcados como corrigidos |
| v2.2 | 05/04/2026 | **BUG-07 e BUG-08 corrigidos** — timer server-side + embaralhamento seguro |
| v2.3 | 05/04/2026 | **Fase 2 concluída** — BUG-09 a BUG-15 marcados como corrigidos |
| v2.4 | 05/04/2026 | **BUG-19 e BUG-20 corrigidos** — moeda pt-BR no template + cascade delete matrícula |
| v2.5 | 05/04/2026 | **BUG-16, BUG-17 e BUG-21 corrigidos** — Fase 3 concluída + busca por CPF |
| v2.6 | 05/04/2026 | **Fase 4 concluída** — BUG-22 e BUG-23 descartados a pedido do cliente |

---

## STATUS DAS FASES

| Fase | Bugs | Status |
|---|---|---|
| **Fase 1 — Segurança Imediata** | BUG-01 a BUG-06 | ✅ **CONCLUÍDA** (05/04/2026) |
| **Fase 2 — Integridade de Dados** | BUG-07 a BUG-15 | ✅ **CONCLUÍDA** (05/04/2026) |
| **Fase 3 — Performance e Dados Corretos** | BUG-16 a BUG-20 | ✅ **CONCLUÍDA** (05/04/2026) |
| **Fase 4 — Funcionalidades Quebradas** | BUG-21 a BUG-23 | ✅ **CONCLUÍDA** (05/04/2026) |
| **Fase 5 — Arquitetura e Manutenibilidade** | BUG-24 a BUG-27 | 🔲 Pendente (aguarda planejamento) |

---

## AMBIENTE DE PRODUÇÃO REAL (Abril 2026)

| Item | Valor |
|---|---|
| Plataforma | PythonAnywhere (substituiu Azure em mar/2026) |
| URL | https://centrodequalificacao2020-create.pythonanywhere.com |
| Banco | SQLite — arquivo `/home/.../alunos/cqp.db` |
| ORM | Flask-SQLAlchemy 2.0 (WAL mode ativado em `db.py`) |
| Python | 3.12 |
| Framework | Flask 3.0 + Flask-Migrate (Alembic) |
| PDF | ReportLab |
| Auth | Werkzeug hash + decorators em `security.py` |
| Deploy | `git pull` + `touch <wsgi_file>.py` |

> ⚠ Arquivos Docker/Nginx no repositório são **artefatos do plano Azure** (nunca usados em produção — podem ser ignorados ou removidos)
> ⚠ `INSTALL.md` descreve self-host com Docker — não é o ambiente atual

Console PythonAnywhere: https://www.pythonanywhere.com/user/centrodequalificacao2020-create/consoles/

---

## STACK RESUMIDA

| Arquivo/Pasta | Responsabilidade |
|---|---|
| `app.py` | `create_app()` factory; registra 10 blueprints |
| `db.py` | SQLAlchemy init; WAL mode; `engine.connect()` |
| `security.py` | `hash_senha`, `verificar_senha`, `@login_required`, `@admin_required`, `@aluno_login_required`, `extensao_permitida` |
| `config.py` | `SECRET_KEY` e `UPLOAD_FOLDER` via `.env`; `MAX_CONTENT_LENGTH = 10 MB` |
| `models.py` | 15 modelos ORM (28 KB — maior arquivo Python) |
| `routes/` | 10 blueprints (ver tabela abaixo) |
| `services/` | `matricula_service.py`, `pdf_service.py` |
| `templates/` | `base.html` + subpasta `aluno/` (portal escuro) |
| `static/style.css` | 32 seções; **seção 32 = tema escuro portal aluno** |
| `migrations/` | Flask-Migrate + Alembic (usar SEMPRE para schema) |

### Blueprints

| Blueprint | Arquivo |
|---|---|
| `auth_bp` | `routes/auth.py` |
| `aluno_bp` | `routes/aluno.py` |
| `cursos_bp` | `routes/cursos.py` |
| `financeiro_bp` | `routes/financeiro.py` |
| `dashboard_bp` | `routes/dashboard.py` |
| `despesas_bp` | `routes/despesas.py` |
| `funcionario_bp` | `routes/funcionario.py` |
| `conteudos_bp` | `routes/conteudos.py` |
| `academico_bp` | `routes/academico.py` |
| `portal_aluno_bp` | `routes/portal_aluno.py` |

---

## REGRAS INEGOCIÁVEIS

> Não violar em nenhuma correção.

- **NUNCA** usar `sqlite3` direto — sempre SQLAlchemy via `db.py`
  - **Exceção documentada:** `academico.py /backup` usa `sqlite3.backup()` — não alterar
- **SEMPRE** `@login_required` / `@aluno_login_required` em rotas de escrita
- **NUNCA** hardcode de senhas ou chaves — sempre via `.env`
- Blueprints para novos módulos — nunca adicionar rotas em `app.py`
- **CSS sempre em `static/style.css`** — nunca `style=""` inline nos templates
- Tema do portal aluno: **SEMPRE dentro de `body.tema-aluno { }`** na seção 32 do `style.css`
- Migrations **SEMPRE** via `flask db migrate` + `flask db upgrade` no console do PythonAnywhere — nunca scripts `migrate_*.py` avulsos

---

## COMO FAZER DEPLOY DE QUALQUER CORREÇÃO

```bash
# No console Bash do PythonAnywhere:
cd ~/alunos
git pull

# Se a correção incluir mudança de schema (models.py):
flask db migrate -m "descricao curta"
flask db upgrade

# Recarregar a aplicação:
touch /var/www/centrodequalificacao2020-create_pythonanywhere_com_wsgi.py
```

---

## PLANO MESTRE DE CORREÇÕES

**Legenda:**
- **Risco:** baixo (1–5 linhas, sem efeito colateral) | médio (mudar lógica, testar) | alto (schema ou lógica central)
- **Esforço:** P ≤30 min | M 30–90 min | G >90 min
- **Schema?** S = requer `flask db migrate` + `flask db upgrade`

---

## FASE 1 — SEGURANÇA IMEDIATA ✅ CONCLUÍDA

> **Todos os 6 bugs desta fase foram corrigidos em 05/04/2026.**
> Sem mudança de banco. Total estimado: ~45 min.

---

### BUG-01 ★ CRÍTICO · Precedência de operador — admin vê menu de aluno
✅ **CORRIGIDO em 05/04/2026** — `templates/base.html`
> Parênteses adicionados: `{% if perfil == "aluno" or (session.aluno_id and not session.usuario_id) %}`

- **Arquivo:** `templates/base.html` (~linha 45)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min

---

### BUG-02 ★ CRÍTICO · localStorage vaza última aula entre alunos
✅ **CORRIGIDO em 05/04/2026** — `templates/aluno/curso_detalhe.html`
> Todas as ocorrências de `localStorage` substituídas por `sessionStorage`.

- **Arquivo:** `templates/aluno/curso_detalhe.html`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min

---

### BUG-03 ★ CRÍTICO · Ex-aluno mantém acesso após exclusão
✅ **CORRIGIDO em 05/04/2026** — `routes/aluno.py`
> `Usuario` vinculado (`perfil="aluno"`) agora é excluído junto com o `Aluno`.

- **Arquivo:** `routes/aluno.py` → `excluir_aluno()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-04 ★ CRÍTICO · Fallback de auth por nome — conta errada para homônimos
✅ **CORRIGIDO em 05/04/2026** — `routes/auth.py`
> Bloco de fallback por nome removido. Retorna `None` com log de warning.

- **Arquivo:** `routes/auth.py` → `_vincular_aluno()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-05 ★ CRÍTICO · Fallback except ignora permissão de conteúdo
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> `except` agora loga o erro e retorna lista vazia com flash de aviso.

- **Arquivo:** `routes/portal_aluno.py` → `curso_detalhe()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-06 · Upload sem validação de tipo no template
✅ **CORRIGIDO em 05/04/2026** — `templates/aluno/curso_detalhe.html`
> Atributo `accept="..."` adicionado nos inputs de arquivo.

- **Arquivo:** `templates/aluno/curso_detalhe.html`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min

---

## FASE 2 — INTEGRIDADE DE DADOS ✅ CONCLUÍDA

> **Todos os 9 bugs desta fase foram corrigidos em 05/04/2026.**
> Sem mudança de banco. Total estimado: ~3 horas.

---

### BUG-07 ★ CRÍTICO · Timer de prova controlado só no frontend
✅ **CORRIGIDO em 05/04/2026** — `routes/provas_aluno.py` + `templates/aluno/provas_realizar.html`
> Timestamp assinado com HMAC-SHA256 no servidor; tolerância de 30s; nota 0 se expirado.

- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 45 min

---

### BUG-08 ★ CRÍTICO · Correção de prova errada por embaralhamento no browser
✅ **CORRIGIDO em 05/04/2026** — `routes/provas_aluno.py` + `templates/aluno/provas_realizar.html`
> Embaralhamento movido para Python (`random.shuffle`); ordem assinada com HMAC-SHA256.

- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 60 min

---

### BUG-09 · lancar_mensalidade() chama criar_matricula() indevidamente
✅ **CORRIGIDO em 05/04/2026** — `routes/financeiro.py` + `services/matricula_service.py`
> Flag `apenas_mensalidade=1` trata modo avulso sem criar novo registro `Matricula`.

- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 30 min

---

### BUG-10 · Comparação de datas como string em _contar_atrasadas()
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> Usa `date.today()` direto; converte `m.vencimento` com `isinstance` check.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-11 · concluir_aula() redireciona para curso errado
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> Recebe `curso_id` via query param; fallback filtra pela matrícula ativa do aluno.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

---

### BUG-12 · Validação de nota sem range (valores impossíveis)
✅ **CORRIGIDO em 05/04/2026** — `routes/academico.py`
> Rejeita valores fora de 0.0–10.0 com `ValueError`.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-13 · Validação de data futura em frequência ausente
✅ **CORRIGIDO em 05/04/2026** — `routes/academico.py`
> Lança `ValueError` se `data_aula > date.today()`.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-14 · Transações sem rollback explícito em services
✅ **CORRIGIDO em 05/04/2026** — `services/matricula_service.py`
> `try/except` com `rollback` + `re-raise` em `criar_matricula()`.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 20 min

---

### BUG-15 · Logging ausente nos excepts críticos
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> `dashboard_aluno()` e `notas_aluno()` agora logam o erro antes de continuar.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

---

## FASE 3 — PERFORMANCE E DADOS CORRETOS ✅ CONCLUÍDA

> **Todos os 5 bugs desta fase foram corrigidos em 05/04/2026.**
> Sem mudança de schema. Baixo risco.

---

### BUG-16 · N+1 queries: atividades sem eager loading
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> `joinedload(Atividade.questoes)` adicionado em `curso_detalhe()`.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-17 · _buscar_aluno_por_login() faz full table scan
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> Pré-filtro SQL pelos últimos 4 dígitos do CPF evita `Aluno.query.all()`.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

---

### BUG-18 · Política de acesso indefinida quando MateriaLiberada está vazia
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> Política B: sem registro de `MateriaLiberada` = acesso total.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

---

### BUG-19 · Formato monetário inconsistente no portal do aluno
✅ **CORRIGIDO em 05/04/2026** — `templates/aluno/financeiro.html`
> `{{ valor|moeda }}` substitui `'%.2f'|format(valor)`. Resultado: `R$ 150,00`.

- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 20 min

---

### BUG-20 · Cascade delete ausente: filhos órfãos ao cancelar matrícula
✅ **CORRIGIDO em 05/04/2026** — `routes/aluno.py`
> 4 DELETEs explícitos antes do commit: `Mensalidade`, `MateriaLiberada`, `acesso_conteudo_curso`, `Matricula`.

- **Esforço:** P | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 30 min

---

## FASE 4 — FUNCIONALIDADES QUEBRADAS ✅ CONCLUÍDA

> **Fase concluída em 05/04/2026.**
> BUG-21 corrigido. BUG-22 e BUG-23 descartados a pedido do cliente.

---

### BUG-21 · Filtro de busca de alunos ignora CPF
✅ **CORRIGIDO em 05/04/2026** — `routes/aluno.py`
> `db.or_` pesquisa por nome (`ilike`) e CPF (`like`) simultaneamente.

- **Arquivo:** `routes/aluno.py` → `cadastro()` (GET)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

---

### BUG-22 · Relatório mensal não exclui cancelamentos
🗑️ **DESCARTADO** — cliente não utiliza status de cancelamento; matrículas são excluídas diretamente.

---

### BUG-23 · Export CSV sem encoding correto
🗑️ **DESCARTADO** — funcionalidade de export CSV não é necessária para o cliente.

---

## FASE 5 — ARQUITETURA E MANUTENIBILIDADE

> Aguarda planejamento separado. Nenhuma das correções desta fase tem impacto funcional imediato.
> Nenhum bug desta fase requer mudança de schema.

---

### BUG-24 · models.py monolítico (28 KB)
🔲 **PENDENTE**

- **Arquivo:** `models.py`
- **Esforço:** G | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 90 min
- Separar em `models/` com `__init__.py` re-exportando tudo.

---

### BUG-25 · Sem paginação em listagens longas
🔲 **PENDENTE**

- **Arquivo:** `routes/financeiro.py`
- **Esforço:** M | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 45 min
- Usar `.paginate(page=page, per_page=50)` do Flask-SQLAlchemy.

---

### BUG-26 · SECRET_KEY sem fallback seguro em desenvolvimento
🔲 **PENDENTE**

- **Arquivo:** `config.py`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min

**Correção:**
```python
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
if not os.environ.get("SECRET_KEY"):
    import warnings
    warnings.warn("SECRET_KEY não definida — usando chave temporária (sessões resetam a cada deploy)")
```

---

### BUG-27 · Arquivos Docker/Nginx obsoletos no repositório
🔲 **PENDENTE**

- **Arquivo:** `Dockerfile`, `docker-compose.yml`, `nginx.conf` (raiz do repo)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min
- Mover para `_legado/azure/` ou remover. Adicionar nota no `README.md`.
