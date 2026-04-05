# RELATÓRIO FINAL CONSOLIDADO v2.4 — Sistema CQP "alunos"
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

---

## STATUS DAS FASES

| Fase | Bugs | Status |
|---|---|---|
| **Fase 1 — Segurança Imediata** | BUG-01 a BUG-06 | ✅ **CONCLUÍDA** (05/04/2026) |
| **Fase 2 — Integridade de Dados** | BUG-07 a BUG-15 | ✅ **CONCLUÍDA** (05/04/2026) |
| **Fase 3 — Performance e Dados Corretos** | BUG-16 a BUG-20 | 🔄 **PARCIAL** — BUG-19 ✅ BUG-20 ✅ · BUG-16/17/18 pendentes |
| **Fase 4 — Funcionalidades Quebradas** | BUG-21 a BUG-23 | 🔲 Pendente |
| **Fase 5 — Arquitetura e Manutenibilidade** | BUG-24 a BUG-27 | 🔲 Pendente |

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

**Problema:**
```jinja
{% if perfil == "aluno" or session.aluno_id and not session.usuario_id %}
```
Jinja2 avalia: `(perfil=="aluno") OR (session.aluno_id AND NOT usuario_id)`. Admin com `aluno_id` residual na sessão passa na segunda condição.

**Correção:**
```jinja
{% if perfil == "aluno" or (session.aluno_id and not session.usuario_id) %}
```

---

### BUG-02 ★ CRÍTICO · localStorage vaza última aula entre alunos
✅ **CORRIGIDO em 05/04/2026** — `templates/aluno/curso_detalhe.html`
> Todas as ocorrências de `localStorage` substituídas por `sessionStorage`. Comentário `/* BUG-02 */` inline.

- **Arquivo:** `templates/aluno/curso_detalhe.html`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min

**Problema:** `localStorage.setItem('aula_{{ curso.id }}', id)` — `localStorage` persiste após logout do Flask. Em dispositivo compartilhado, aluno B abre aula de A.

**Correção:** Substituir **todas** as ocorrências de `localStorage` por `sessionStorage` no template.

---

### BUG-03 ★ CRÍTICO · Ex-aluno mantém acesso após exclusão
✅ **CORRIGIDO em 05/04/2026** — `routes/aluno.py`
> `Usuario` vinculado (`perfil="aluno"`) agora é excluído junto com o `Aluno`. Comentário `# BUG-03` inline.

- **Arquivo:** `routes/aluno.py` → `excluir_aluno()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Problema:** A função exclui `Matricula`, `Nota`, `Frequencia`, `Mensalidade`, etc., mas **nunca** exclui o `Usuario` vinculado (`perfil="aluno"`).

**Correção** (inserida antes do `db.session.commit()` final):
```python
usuario = Usuario.query.filter_by(
    aluno_id=aluno.id, perfil="aluno"
).first()
if usuario:
    db.session.delete(usuario)
# db.session.commit() já existente logo abaixo
```

---

### BUG-04 ★ CRÍTICO · Fallback de auth por nome — conta errada para homônimos
✅ **CORRIGIDO em 05/04/2026** — `routes/auth.py`
> Bloco de fallback por nome removido. Agora retorna `None` com log de warning se aluno não encontrado por email. Comentário `# BUG-04` inline.

- **Arquivo:** `routes/auth.py` → `_vincular_aluno()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Problema:**
```python
if not aluno:
    aluno = Aluno.query.filter_by(nome=user.nome).first()
```
Fallback por nome não é identificador único. Dois "Maria Silva" = aluno B acessa financeiro de A.

**Correção:** Fallback por nome removido. Mantida apenas busca por email:
```python
aluno = Aluno.query.filter(
    db.func.lower(Aluno.email) == user.email.lower()
).first()
if not aluno:
    app.logger.warning(f"Login sem aluno vinculado: {user.email}")
    return None
```

---

### BUG-05 ★ CRÍTICO · Fallback except ignora permissão de conteúdo
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> `except` agora loga o erro e retorna lista vazia com flash de aviso, sem carregar conteúdo não autorizado. Comentário `# BUG-05` inline.

- **Arquivo:** `routes/portal_aluno.py` → `curso_detalhe()` ou equivalente
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Problema:**
```python
except Exception:
    atividades = Atividade.query.filter_by(curso_id=...).all()
```
Fallback carrega **todas** as atividades ignorando `AtividadeLiberada`.

**Correção:**
```python
except Exception as e:
    app.logger.error(f"Erro ao carregar atividades: {e}", exc_info=True)
    atividades = []
    flash("Erro ao carregar conteúdo. Tente novamente.", "error")
```

---

### BUG-06 · Upload sem validação de tipo no template
✅ **CORRIGIDO em 05/04/2026** — `templates/aluno/curso_detalhe.html`
> Atributo `accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.zip"` adicionado nos 3 inputs de arquivo. Comentário `{# BUG-06 #}` inline.

- **Arquivo:** `templates/aluno/curso_detalhe.html`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min
- **Nota:** `security.py` já tem `extensao_permitida()` — validação server-side mantida. Esta correção é apenas reforço client-side.

**Correção** (nos inputs de entrega de atividade):
```html
<input type="file" name="arquivo1"
       accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.zip">
```

---

## FASE 2 — INTEGRIDADE DE DADOS ✅ CONCLUÍDA

> **Todos os 9 bugs desta fase foram corrigidos em 05/04/2026.**
> Sem mudança de banco. Total estimado: ~3 horas.

---

### BUG-07 ★ CRÍTICO · Timer de prova controlado só no frontend
✅ **CORRIGIDO em 05/04/2026** — `routes/provas_aluno.py` + `templates/aluno/provas_realizar.html`

> **Solução implementada:**
> - No GET, o servidor gera um timestamp de início assinado com HMAC-SHA256 (chave = `SECRET_KEY`) e envia ao template como campo oculto `token_inicio`.
> - No POST, o servidor extrai e verifica o token. Se inválido (adulterado) → rejeita. Se o tempo decorrido ultrapassar `prova.tempo_limite + 30s de tolerância` → registra tentativa consumida com nota 0 e redireciona.
> - O cronômetro no frontend continua existindo como UX, mas a autoridade é exclusivamente o servidor.
> - **Sem mudança de schema** — usa `iniciado_em` (String 19) já existente em `RespostaProva`.

- **Arquivo:** `routes/provas_aluno.py` + `templates/aluno/provas_realizar.html`
- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não (adaptado para usar campo existente) | **Tempo:** 45 min

---

### BUG-08 ★ CRÍTICO · Correção de prova errada por embaralhamento no browser
✅ **CORRIGIDO em 05/04/2026** — `routes/provas_aluno.py` + `templates/aluno/provas_realizar.html`

> **Solução implementada:**
> - O embaralhamento de alternativas foi movido do JavaScript para o Python (`random.shuffle` no GET).
> - A ordem embaralhada é serializada como JSON e assinada com HMAC-SHA256, enviada ao template como campo oculto `token_ordem`.
> - O template renderiza as alternativas na ordem recebida do servidor (`item.alts`), não mais via `Math.random()`.
> - A submissão continua enviando o `alt.id` (ID real da alternativa no banco). A correção server-side compara `alt_id == correta.id` — portanto **sempre correta**, independente da ordem visual.
> - O token assinado permite que o servidor verifique a ordem exibida se necessário (auditoria futura).

- **Arquivo:** `routes/provas_aluno.py` + `templates/aluno/provas_realizar.html`
- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 60 min

---

### BUG-09 · lancar_mensalidade() chama criar_matricula() indevidamente
✅ **CORRIGIDO em 05/04/2026** — `routes/financeiro.py` + `services/matricula_service.py`
> Flag `apenas_mensalidade=1` adicionada ao form de lançamento avulso; `financeiro.py` passa a flag ao `criar_matricula()`, que trata o modo avulso sem criar novo registro `Matricula`.

- **Arquivo:** `routes/financeiro.py` → `lancar_mensalidade()` + `services/matricula_service.py`
- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 30 min

---

### BUG-10 · Comparação de datas como string em _contar_atrasadas()
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> Usa `date.today()` direto; converte `m.vencimento` com `isinstance` check antes de comparar.

- **Arquivo:** `routes/portal_aluno.py` → `_contar_atrasadas()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-11 · concluir_aula() redireciona para curso errado
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> Recebe `curso_id` via query param; fallback filtra `CursoMateria` pela matrícula ativa do aluno em vez de pegar o primeiro registro.

- **Arquivo:** `routes/portal_aluno.py` → `concluir_aula()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

---

### BUG-12 · Validação de nota sem range (valores impossíveis)
✅ **CORRIGIDO em 05/04/2026** — `routes/academico.py`
> Converte para float; rejeita valores fora de 0.0–10.0 com `ValueError`.

- **Arquivo:** `routes/academico.py` → `salvar_nota()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-13 · Validação de data futura em frequência ausente
✅ **CORRIGIDO em 05/04/2026** — `routes/academico.py`
> Lança `ValueError` se `data_aula > date.today()`.

- **Arquivo:** `routes/academico.py` → `registrar_frequencia()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

---

### BUG-14 · Transações sem rollback explícito em services
✅ **CORRIGIDO em 05/04/2026** — `services/matricula_service.py`
> Bloco `try/except` envolve todo o corpo de `criar_matricula()`; `rollback` + `re-raise` no `except`.

- **Arquivo:** `services/matricula_service.py`
- **Esforço:** P por função | **Risco:** BAIXO | **Schema:** Não | **Tempo:** ~20 min total

---

### BUG-15 · Logging ausente nos excepts críticos
✅ **CORRIGIDO em 05/04/2026** — `routes/portal_aluno.py`
> `dashboard_aluno()` e `notas_aluno()` agora logam o erro antes de continuar.

- **Arquivo:** `routes/portal_aluno.py` (múltiplos pontos)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min total

---

## FASE 3 — PERFORMANCE E DADOS CORRETOS 🔄 PARCIAL

> BUG-19 e BUG-20 corrigidos em 05/04/2026. BUG-16, BUG-17 e BUG-18 pendentes.
> Sem mudança de schema (exceto BUG-20). Baixo risco. Total estimado restante: ~40 min.

### BUG-16 · N+1 queries: atividades sem eager loading
🔲 **PENDENTE**

- **Arquivo:** `routes/portal_aluno.py`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Correção:**
```python
from sqlalchemy.orm import joinedload
atividades = Atividade.query \
    .options(joinedload(Atividade.questoes)) \
    .filter_by(curso_id=curso_id, ativa=1).all()
```

---

### BUG-17 · _buscar_aluno_por_login() faz full table scan
🔲 **PENDENTE**

- **Arquivo:** `routes/portal_aluno.py` → `_buscar_aluno_por_login()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min
- **Nota:** `Aluno.query.all()` carrega TODOS os alunos por login. SQLite com WAL aguenta ~500 alunos; acima disso lentidão.

**Correção:**
```python
import re
cpf_limpo = re.sub(r'\D', '', identificador)
alunos_candidatos = Aluno.query.filter(
    db.or_(
        Aluno.email == identificador,
        Aluno.cpf.like(f"%{cpf_limpo[-4:]}%")  # pré-filtro
    )
).all()
# Depois filtrar em Python para match exato de CPF normalizado
```

---

### BUG-18 · Política de acesso indefinida quando MateriaLiberada está vazia
🔲 **PENDENTE**

- **Arquivo:** `routes/portal_aluno.py` → `_curso_tem_acesso()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

**Decisão necessária antes de corrigir:**
- Política A: sem registro = acesso **NEGADO** (mais seguro)
- Política B: sem registro = acesso **LIBERADO** (mais prático para escola pequena)

**Correção (Política B — recomendada):**
```python
def _curso_tem_acesso(aluno_id, curso_id):
    count = MateriaLiberada.query.filter_by(
        aluno_id=aluno_id, curso_id=curso_id
    ).count()
    return count == 0  # sem restrições = acesso total
    # Se quiser Política A: return count > 0
```

---

### BUG-19 · Formato monetário inconsistente no portal do aluno
✅ **CORRIGIDO em 05/04/2026** — `templates/aluno/financeiro.html`
> Todas as ocorrências de `'%.2f'|format(valor)` substituídas pelo filtro `{{ valor|moeda }}` já registrado em `app.py`. Resultado: `R$ 150,00` em vez de `R$ 150.0`.

- **Arquivo:** `templates/aluno/financeiro.html`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 20 min

---

### BUG-20 · Cascade delete ausente: filhos órfãos ao cancelar matrícula
✅ **CORRIGIDO em 05/04/2026** — `routes/aluno.py`
> `excluir_matricula()` agora executa 4 DELETEs em sequência antes do commit: `Mensalidade`, `MateriaLiberada`, `acesso_conteudo_curso` e por último a `Matricula` em si. Sem alteração de schema.

- **Arquivo:** `routes/aluno.py` → `excluir_matricula()`
- **Esforço:** P | **Risco:** MÉDIO | **Schema:** Não (solução via DELETE explícito) | **Tempo:** 30 min

---

## FASE 4 — FUNCIONALIDADES QUEBRADAS

> Bugs que tornam features inutilizáveis. Sem mudança de schema. Total estimado: ~2 horas.

### BUG-21 · Filtro de busca de alunos ignora CPF
🔲 **PENDENTE**

- **Arquivo:** `routes/aluno.py` → listagem/busca
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

**Correção:**
```python
Aluno.query.filter(
    db.or_(
        Aluno.nome.ilike(f"%{q}%"),
        Aluno.cpf.like(f"%{q}%")
    )
).order_by(Aluno.nome).all()
```

---

### BUG-22 · Relatório mensal não exclui cancelamentos
🔲 **PENDENTE**

- **Arquivo:** `routes/dashboard.py` ou `routes/relatorio.py`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 20 min

**Correção:** Adicionar `.filter(Matricula.status != "CANCELADA")` nas queries de contagem.

---

### BUG-23 · Export CSV sem encoding correto (acentos quebrados)
🔲 **PENDENTE**

- **Arquivo:** `routes/aluno.py` ou equivalente → exportar CSV
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Correção:**
```python
output = io.StringIO()
writer = csv.writer(output)
# ...
response = make_response(output.getvalue().encode('utf-8-sig'))  # BOM para Excel
response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
```

---

## FASE 5 — ARQUITETURA E MANUTENIBILIDADE

> Refatorações sem impacto funcional imediato. Total estimado: ~3 horas.

### BUG-24 · models.py monolítico (28 KB)
🔲 **PENDENTE**

- **Arquivo:** `models.py`
- **Esforço:** G | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 90 min
- Separar em `models/` com `__init__.py` re-exportando tudo.

---

### BUG-25 · Sem paginação em listagens longas
🔲 **PENDENTE**

- **Arquivo:** `routes/aluno.py`, `routes/financeiro.py`
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
