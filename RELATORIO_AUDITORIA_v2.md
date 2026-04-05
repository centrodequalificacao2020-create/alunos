# RELATÓRIO FINAL CONSOLIDADO v2 — Sistema CQP "alunos"
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

## FASE 1 — SEGURANÇA IMEDIATA

> Corrigir primeiro. Zero risco de efeito colateral. Sem mudança de banco. Total estimado: ~45 min.

### BUG-01 ★ CRÍTICO · Precedência de operador — admin vê menu de aluno

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

- **Arquivo:** `templates/aluno/curso_detalhe.html` (ou `conteudo.html`)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min

**Problema:** `localStorage.setItem('aula_{{ curso.id }}', id)` — `localStorage` persiste após logout do Flask. Em dispositivo compartilhado, aluno B abre aula de A.

**Correção:** Substituir **todas** as ocorrências de `localStorage` por `sessionStorage` no template. `sessionStorage` é limpo ao fechar o navegador/aba.

---

### BUG-03 ★ CRÍTICO · Ex-aluno mantém acesso após exclusão

- **Arquivo:** `routes/aluno.py` → `excluir_aluno()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Problema:** A função exclui `Matricula`, `Nota`, `Frequencia`, `Mensalidade`, etc., mas **nunca** exclui o `Usuario` vinculado (`perfil="aluno"`).

**Correção** (inserir antes do `db.session.commit()` final):
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

- **Arquivo:** `routes/auth.py` → `_vincular_aluno()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Problema:**
```python
if not aluno:
    aluno = Aluno.query.filter_by(nome=user.nome).first()
```
Fallback por nome não é identificador único. Dois "Maria Silva" = aluno B acessa financeiro de A.

**Correção:** Remover o bloco de fallback por nome completamente. Manter apenas busca por email:
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

- **Arquivo:** `templates/aluno/curso_detalhe.html` (ou `conteudo.html`)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 5 min
- **Nota:** `security.py` já tem `extensao_permitida()` — confirmar se validação server-side já existe antes de duplicar.

**Correção** (nos inputs de entrega de atividade):
```html
<input type="file" name="arquivo1"
       accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.zip">
```

---

## FASE 2 — INTEGRIDADE DE DADOS

> Corrigir após Fase 1. Sem mudança de banco (exceto BUG-07). Testar fluxo afetado. Total estimado: ~3 horas.

### BUG-07 ★ CRÍTICO · Timer de prova controlado só no frontend

- **Arquivo:** `templates/aluno/provas_realizar.html` + `routes/portal_aluno.py` → `submeter_prova()`
- **Esforço:** M | **Risco:** MÉDIO | **Schema:** **SIM** | **Tempo:** 45 min

**Problema:** Aluno recarrega página e obtém tempo completo novamente.

**Correção — Parte A** (`models.py`):
```python
class TentativaProva(db.Model):
    inicio_em = db.Column(db.DateTime, default=datetime.utcnow)
```

**Correção — Parte B** (`submeter_prova`):
```python
tentativa = TentativaProva.query.get(tentativa_id)
tempo_decorrido = datetime.utcnow() - tentativa.inicio_em
if prova.tempo_limite:
    from datetime import timedelta
    if tempo_decorrido > timedelta(minutes=prova.tempo_limite):
        flash("Tempo esgotado.", "warning")
        return redirect(url_for('portal_aluno.provas'))
```

---

### BUG-08 ★ CRÍTICO · Correção de prova errada por embaralhamento no browser

- **Arquivo:** `templates/aluno/provas_realizar.html` + `routes/portal_aluno.py`
- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 60 min

**Problema:** Alternativas embaralhadas via `Math.random()` no JavaScript. Aluno envia letra visual (A/B/C/D embaralhada). Correção server-side compara com letra original do banco → **nota incorreta**.

**Correção** (na rota que carrega a prova):
```python
import random
for q in questoes:
    alts = [
        ('A', q.alt_a), ('B', q.alt_b),
        ('C', q.alt_c), ('D', q.alt_d)
    ]
    random.shuffle(alts)
    q.alts_display = alts  # lista de (letra_visual, texto)
    # Mapear letra visual → letra original para correção
    q.mapa = {chr(65+i): alts[i][0] for i in range(len(alts))}
# Passar mapa para o template (via session ou campo oculto assinado)
# Na correção, traduzir: resposta_original = mapa[resposta_enviada]
```

---

### BUG-09 · lancar_mensalidade() chama criar_matricula() indevidamente

- **Arquivo:** `routes/financeiro.py` → `lancar_mensalidade()` + `services/matricula_service.py`
- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 30 min

**Problema:** Cada lançamento avulso cria matrícula fantasma no banco.

**Correção:** Criar `services/financeiro_service.py`:
```python
def criar_mensalidade_avulsa(aluno_id, valor, vencimento, descricao, tipo):
    m = Mensalidade(
        aluno_id=aluno_id, valor=valor,
        vencimento=vencimento, descricao=descricao,
        tipo=tipo, status="Pendente"
    )
    db.session.add(m)
    db.session.commit()
    return m
```
Em `financeiro.py`, substituir a chamada a `criar_matricula()` pela nova função.

---

### BUG-10 · Comparação de datas como string em _contar_atrasadas()

- **Arquivo:** `routes/portal_aluno.py` → `_contar_atrasadas()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Correção:**
```python
from datetime import date
hoje = date.today()
def _contar_atrasadas(mensalidades):
    return sum(
        1 for m in mensalidades
        if m.status != "Pago" and m.vencimento and
        (m.vencimento if isinstance(m.vencimento, date)
         else date.fromisoformat(str(m.vencimento))) < hoje
    )
```

---

### BUG-11 · concluir_aula() redireciona para curso errado

- **Arquivo:** `routes/portal_aluno.py` → `concluir_aula()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min

**Correção:** Adicionar `curso_id` como parâmetro na URL de conclusão:
```python
curso_id = request.args.get('curso_id', type=int)
if not curso_id:
    mat = Matricula.query.filter_by(
        aluno_id=session['aluno_id'], status='ATIVA'
    ).first()
    curso_id = mat.curso_id if mat else None
return redirect(url_for('portal_aluno.conteudo', curso_id=curso_id))
```

---

### BUG-12 · Validação de nota sem range (valores impossíveis)

- **Arquivo:** `routes/academico.py` → `salvar_nota()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Correção** (na rota, antes do insert):
```python
nota_val = float(request.form.get('nota', 0))
if not (0.0 <= nota_val <= 10.0):
    flash("Nota deve estar entre 0 e 10.", "error")
    return redirect(request.referrer or url_for('academico.notas'))
```

---

### BUG-13 · Validação de data futura em frequência ausente

- **Arquivo:** `routes/academico.py` → `registrar_frequencia()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Correção:**
```python
from datetime import date
data_aula = datetime.strptime(request.form['data'], '%Y-%m-%d').date()
if data_aula > date.today():
    flash("Não é possível registrar frequência para data futura.", "error")
    return redirect(request.referrer)
```

---

### BUG-14 · Transações sem rollback explícito em services

- **Arquivo:** `services/matricula_service.py` + outros services
- **Esforço:** P por função | **Risco:** BAIXO | **Schema:** Não | **Tempo:** ~20 min total

**Padrão a aplicar em cada função de escrita:**
```python
def criar_matricula(dados):
    try:
        # lógica existente sem alteração
        db.session.commit()
        return matricula
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"[criar_matricula] {e}", exc_info=True)
        raise
```

---

### BUG-15 · Logging ausente nos excepts críticos

- **Arquivo:** `routes/` e `services/` (múltiplos pontos)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 15 min total

**Padrão a aplicar em cada `except` que hoje tem `pass` ou só `rollback`:**
```python
except Exception as e:
    db.session.rollback()
    app.logger.error(f"[{request.endpoint}] Erro: {e}", exc_info=True)
    flash("Ocorreu um erro. Tente novamente.", "error")
```

---

## FASE 3 — PERFORMANCE E DADOS CORRETOS

> Sem mudança de schema (exceto BUG-20). Baixo risco. Total estimado: ~1,5 horas.

### BUG-16 · N+1 queries: atividades sem eager loading

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

- **Arquivo:** `app.py` + `templates/aluno/financeiro.html` (e outros)
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 20 min
- **Sintoma:** `"R$ 150.0"` vs `"R$ 150,00"`

**Correção** (em `app.py`, após `create_app`):
```python
@app.template_filter('moeda')
def moeda_filter(value):
    try:
        v = float(value)
        return f"R$ {v:,.2f}".replace(',','X').replace('.',',').replace('X','.')
    except (TypeError, ValueError):
        return "R$ 0,00"
```
Substituir nos templates: `{{ m.valor }}` → `{{ m.valor|moeda }}`

---

### BUG-20 · Cascade delete ausente: filhos órfãos ao cancelar matrícula

- **Arquivo:** `models.py` → `class Matricula`
- **Esforço:** P | **Risco:** MÉDIO | **Schema:** **SIM** | **Tempo:** 30 min

**Correção:**
```python
class Matricula(db.Model):
    mensalidades = db.relationship('Mensalidade',
        backref='matricula', lazy='dynamic',
        cascade='all, delete-orphan',
        foreign_keys='Mensalidade.matricula_id')
    # Repetir para Nota e Frequencia se tiverem matricula_id
```

---

## FASE 4 — FUNCIONALIDADES QUEBRADAS

> Sem risco de regressão. Melhorias visíveis para o usuário. Total estimado: ~1 hora.

### BUG-21 · Backup SQLite — verificar path no PythonAnywhere

- **Arquivo:** `routes/academico.py` → `/backup`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Verificação primeiro:**
```bash
# No console PA:
python3 -c "from app import create_app; a=create_app(); print(a.config['SQLALCHEMY_DATABASE_URI'])"
```
Confirmar path do `cqp.db` e comparar com o hardcoded em `/backup`.

**Correção (se path errado):**
```python
import os
db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
src = sqlite3.connect(db_path)
# resto da lógica existente sem alteração
```

---

### BUG-22 · Paginação ausente na listagem de alunos

- **Arquivo:** `routes/aluno.py` → `GET /cadastro`
- **Esforço:** M | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 45 min
- **Sintoma:** Com 200+ alunos, página lenta; com 1000+, timeout no PA.

**Correção:**
```python
page = request.args.get('page', 1, type=int)
alunos = Aluno.query.order_by(Aluno.nome) \
    .paginate(page=page, per_page=30, error_out=False)
# No template: iterar alunos.items
# Adicionar controles de paginação (prev/next)
```

---

### BUG-23 · Validação de dupla matrícula ativa ausente

- **Arquivo:** `services/matricula_service.py` → `criar_matricula()`
- **Esforço:** P | **Risco:** BAIXO | **Schema:** Não | **Tempo:** 10 min

**Correção** (no início de `criar_matricula`):
```python
existente = Matricula.query.filter_by(
    aluno_id=dados['aluno_id'],
    curso_id=dados['curso_id'],
    status='ATIVA'
).first()
if existente:
    raise ValueError("Aluno já possui matrícula ativa neste curso.")
```

---

## FASE 5 — ARQUITETURA E MANUTENIBILIDADE

> Sem urgência. Executar quando o sistema estiver estável. Total estimado: ~8 horas.

### BUG-24 · Permissões de menu inconsistentes com os decorators das rotas

- **Arquivo:** `templates/base.html` + `security.py`
- **Esforço:** G | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 90 min
- **Sintoma:** Secretaria vê links que resultam em 403.

**Correção:**
```python
# Em security.py:
PERMISSOES = {
    'admin': ['*'],
    'financeiro': ['financeiro','cadastro','relatorio','dashboard'],
    'secretaria': ['cadastro','turmas','materias','conteudos','notas','frequencia'],
    'instrutor': ['turmas','materias','conteudos','notas','frequencia'],
}
# Em base.html: {% if tem_permissao(perfil, 'financeiro') %}
```

---

### BUG-25 · Scripts migrate*.py avulsos na raiz (13 arquivos)

- **Arquivo:** `migrate*.py` (13 arquivos na raiz)
- **Esforço:** M | **Risco:** ALTO se executados — ZERO se apenas movidos | **Schema:** Não | **Tempo:** 30 min

**Ação segura:**
1. **NÃO** executar nenhum `migrate_*.py` — Flask-Migrate já está ativo
2. Mover para `scripts/legacy/` com comentário no topo: `# ATENÇÃO: aplicado em [data]. NÃO reexecutar.`
3. A partir de agora, TODA mudança de schema via `flask db migrate` + `flask db upgrade`

---

### BUG-26 · Lógica de negócio embutida em templates grandes

- **Arquivos:** `templates/provas.html` (28 KB), `exercicio_questoes.html`, `liberacoes.html`
- **Esforço:** G | **Risco:** ALTO | **Schema:** Não | **Tempo:** 3–4 horas

**Estratégia:**
```python
# Criar services/prova_service.py
def preparar_provas_aluno(aluno_id, curso_id):
    # Retorna lista de dicts:
    # [{'prova': p, 'pode_fazer': bool, 'tentativas': n, ...}]
    pass
# Template recebe dicts simples e apenas exibe — sem lógica
```

---

### BUG-27 · CSS inline nos templates do portal quebra encapsulamento

- **Arquivo:** `templates/aluno/` (vários com `<style>` embutido)
- **Esforço:** G | **Risco:** MÉDIO | **Schema:** Não | **Tempo:** 2–3 horas
- **Regra:** `PROJECT_BRIEF` diz "CSS sempre em `static/style.css`". Os `<style>` inline são violações.

**Ação:** Mover todo CSS inline para a seção 32 do `style.css` (`body.tema-aluno`), testando visual após cada migração.

---

## TABELA RESUMO — ORDEM DE EXECUÇÃO

| Fase | Bug | Descrição resumida | Impacto | Esforço | Risco | Schema | Tempo |
|---|---|---|---|---|---|---|---|
| F1 | B-01 | Precedência operador menu base.html | CRÍTICO | P | BAIXO | Não | 5 min |
| F1 | B-02 | localStorage → sessionStorage | CRÍTICO | P | BAIXO | Não | 5 min |
| F1 | B-03 | Excluir Usuario ao excluir Aluno | CRÍTICO | P | BAIXO | Não | 10 min |
| F1 | B-04 | Remover fallback login por nome | CRÍTICO | P | BAIXO | Não | 10 min |
| F1 | B-05 | Remover except que ignora permissão | CRÍTICO | P | BAIXO | Não | 10 min |
| F1 | B-06 | accept= nos inputs de arquivo | ALTO | P | BAIXO | Não | 5 min |
| F2 | B-07 | Timer de prova server-side | CRÍTICO | M | MÉDIO | **SIM** | 45 min |
| F2 | B-08 | Embaralhamento alternativas no servidor | CRÍTICO | M | MÉDIO | Não | 60 min |
| F2 | B-09 | Separar lançamento avulso de criar_matricula | ALTO | M | MÉDIO | Não | 30 min |
| F2 | B-10 | Comparação de datas robusta | MÉDIO | P | BAIXO | Não | 10 min |
| F2 | B-11 | curso_id na URL de concluir_aula | MÉDIO | P | BAIXO | Não | 15 min |
| F2 | B-12 | Validação de range em nota | ALTO | P | BAIXO | Não | 10 min |
| F2 | B-13 | Bloquear data futura em frequência | MÉDIO | P | BAIXO | Não | 10 min |
| F2 | B-14 | try/except/rollback em services | ALTO | P | BAIXO | Não | 20 min |
| F2 | B-15 | logger.error nos excepts | ALTO | P | BAIXO | Não | 15 min |
| F3 | B-16 | joinedload em atividades.questoes | MÉDIO | P | BAIXO | Não | 10 min |
| F3 | B-17 | Corrigir full table scan no login | MÉDIO | P | BAIXO | Não | 15 min |
| F3 | B-18 | Política explícita MateriaLiberada vazia | ALTO | P | BAIXO | Não | 15 min |
| F3 | B-19 | Filtro Jinja2 \|moeda uniforme | BAIXO | P | BAIXO | Não | 20 min |
| F3 | B-20 | Cascade delete Matricula → filhos | MÉDIO | P | MÉDIO | **SIM** | 30 min |
| F4 | B-21 | Verificar path do backup SQLite no PA | ALTO | P | BAIXO | Não | 10 min |
| F4 | B-22 | Paginação listagem de alunos | MÉDIO | M | MÉDIO | Não | 45 min |
| F4 | B-23 | Bloquear dupla matrícula ativa | ALTO | P | BAIXO | Não | 10 min |
| F5 | B-24 | Centralizar permissões de menu | BAIXO | G | MÉDIO | Não | 90 min |
| F5 | B-25 | Mover migrate_*.py para scripts/legacy/ | BAIXO | M | BAIXO | Não | 30 min |
| F5 | B-26 | Extrair lógica de provas.html para service | BAIXO | G | ALTO | Não | 4 horas |
| F5 | B-27 | CSS inline → seção 32 style.css | BAIXO | G | MÉDIO | Não | 3 horas |

**Totais:** F1 ~45 min · F2 ~3 h · F3 ~1,5 h · F4 ~1 h · F5 ~8 h

---

## BUGS REMOVIDOS DO RELATÓRIO ANTERIOR

- **BUG-10 anterior** (backup SQLite inoperante): REMOVIDO — `sqlite3.backup()` é intencional e funciona corretamente com SQLite. Substituído por BUG-21 (verificar path no PythonAnywhere).
- **BUG-24 anterior** (migrate para Flask-Migrate): REMOVIDO — Flask-Migrate já está instalado e configurado. Substituído por BUG-25 (organizar os `migrate_*.py` legados).

---

## RISCOS ESTRUTURAIS

### RISCO-A: SQLite em produção
SQLite não suporta acesso concorrente de múltiplos workers. No PythonAnywhere, Gunicorn com >1 worker pode causar `"database is locked"` em horários de pico.
- **Mitigação imediata:** `db.py` já usa WAL mode ✅
- **Mitigação definitiva:** migrar para PostgreSQL (plano futuro)

### RISCO-B: Arquivo cqp.db no filesystem do PA
Risco de perda em caso de conta expirada ou migração.
- **Mitigação:** automatizar backup periódico via scheduled task no PA (cron) que copia `cqp.db` para pasta separada + download manual semanal.

### RISCO-C: Manutenção sem contexto
Qualquer sessão de IA que não carregar este documento continuará introduzindo bugs colaterais.
- **Mitigação:** usar este arquivo como context obrigatório. Instrução para IA: *"Leia o RELATORIO_AUDITORIA_v2.md antes de qualquer correção."*

### RISCO-D: Ausência total de testes
Nenhum teste automatizado. Qualquer correção pode quebrar funcionalidade adjacente sem ser detectada.
- **Mitigação mínima:** 5 testes de smoke para os fluxos críticos:
  1. Login admin
  2. Login aluno
  3. Criar matrícula
  4. Registrar pagamento
  5. Aluno acessa conteúdo

---

## FIM DO RELATÓRIO

**Versão 2.0 · Abril 2026**
Baseado em: Sessões S2–S6 de análise do repositório + confirmação do ambiente real (PythonAnywhere + SQLite)

- Bugs catalogados: 27
- Bugs removidos/revisados da v1 (contexto incorreto): 2
- Estimativa total Fases 1–4: **~6 horas de trabalho técnico**
