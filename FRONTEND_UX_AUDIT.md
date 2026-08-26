# FRONTEND_UX_AUDIT.md
_Auditoria de frontend, UI/UX e manutenibilidade — Sistema Escolar CQP_
_Gerado na Sessão 5 — 26/08/2026 | Diagnóstico por inspeção do código real (46 templates Jinja2 + CSS + JS)_

---

## 0. Escopo e método

Este documento é um **diagnóstico focado** do frontend do sistema (administração + portal do aluno). Ele NÃO propõe reescrever nada — apenas registra o estado atual, classifica os pontos de atenção por severidade e sugere um plano de ciclos para melhoria incremental, sempre verificando o código real.

**O que foi inspecionado:**
- `static/style.css` (1235 linhas) + `static/css/portal_aluno.css` (190 linhas)
- `static/js/cadastro.js` (194) + `static/js/financeiro.js` (46)
- 46 templates Jinja2 em `templates/` (amostra de 8 representativos: `base.html`, `login.html`, `home.html`, `dashboard.html`, `financeiro.html`, `ficha_aluno.html`, `provas.html`, `exercicio_questoes.html`)

**Contexto técnico (não muda):**
- Server-rendered (Jinja2), **não** é SPA.
- Vanilla CSS com sistema de variáveis próprio (`--color-*`, `--radius-*`, `--shadow-*` em `:root`).
- O backend já é **altamente verificável** (ver `SYSTEM_CONTEXT.md` v5 — DT-03, DT-09, DT-14, DT-16). Este documento cobre o frontend.

---

## 1. Vertentes de análise

### 1.1 Manutenibilidade do frontend

| Aspecto | Estado | Severidade |
|:---|:---|:---|
| **CSS core** | Bem estruturado: variáveis em `:root`, nomes BEM-ish (`portal-sidebar__item`, `aula-card--concluida`), comentários por seção. Base sólida. | 🟢 Boa |
| **CSS inline nos templates** | `dashboard.html`, `provas.html`, `exercicio_questoes.html`, `home.html`, `relatorio.html`, `login.html`, `provas_corrigir.html` têm blocos `<style>` grandes por página. Estilo duplicado entre `provas.html` e `exercicio_questoes.html` (mesmos `.prova-badge-*`, `.tipo-multipla`, `.tipo-vf`). | 🟠 Alta |
| **Cores hardcoded** | `#2c3e50`, `#7f8c8d` (dashboard), `#0f2027/#203a43/#2c5364` (login/home — gradiente repetido), `#0f1923` (provas_corrigir), `#1d4ed8`, `#15803d`, `#7b1fa2`, `#6b7280` em vários templates. Não centralizadas em `:root`. | 🟠 Alta |
| **`!important`** | Uso em `login.html` (`.login-page`, `.login-card`) e `home.html` para sobrepor o core. Sinal de luta contra a cascata. | 🟡 Média |
| **Duplicação de componentes** | ~10 variações de card/badge (`home-card`, `curso-card`, `form-card`, `status-badge`, `prova-badge`, `ex-badge-*`, `accordion-badge`, `material-card`, `q-card`, `aula-card`). Muitas com estilos quase idênticos, definidos em arquivos diferentes. | 🟠 Alta |
| **Padrões repetidos entre templates** | O mesmo bloco de tabela/formulário é copiado de template para template (ex.: listagem de tabela no admin). Manutenção em 46 arquivos. | 🟡 Média |
| **Fontes** | `--font-base: Arial, Helvetica, sans-serif` em `style.css`. Números em fonte proporcional (sem `tabular-nums`). Problema para painel financeiro (tabelas de mensalidades/parcelas). | 🟡 Média |

### 1.2 Manutenibilidade do backend (recorte — ver `SYSTEM_CONTEXT.md` v5 para o completo)

| Aspecto | Estado | Severidade |
|:---|:---|:---|
| **RBAC** (DT-09) | `@login_required` sem validar `perfil` em várias rotas. Melhorias pontuais em `dashboard.py` (completo), `funcionario.py`, `cursos.py`, `atividades.py`. | 🟠 Alta |
| **Import circular** (DT-14) | `from models import ...` dentro de funções em várias rotas. | 🟡 Média |
| **Erro inconsistente** (DT-16) | `except OperationalError` vs `except Exception` vs sem tratamento; mensagens vazam detalhes. | 🟡 Média |
| **Lógica duplicada** (DT-03, DT-15, DT-20) | `_calcular_nota` em 3 rotas; lógica de exercícios duplicada; `aluno.py` duplica matrícula. | 🟠 Alta |
| **Input sem validação** (DT-22) | `float()`/`int()` em `cursos.py`/`despesas.py` sem `try/except` → 500. | 🟡 Média |

**Observação:** O frontend não resolve os problemas do backend. A manutenibilidade real do sistema é majoritariamente determinada pelo backend (DT-09, DT-03, DT-22). O frontend é secundário.

### 1.3 UI/UX design

| Aspecto | Estado | Severidade |
|:---|:---|:---|
| **Tipografia** | Arial, sem escala tipográfica definida, sem `tabular-nums`, sem balanceamento de texto (`.card-header h2`, `.home-card span`). | 🟠 Alta |
| **Padrão visual** | Fundo `var(--color-surface)` (cinza claro) consistente no admin. Contraste: o **login e home usam gradiente escuro "AI"** (`#0f2027 → #2c5364` com `backdrop-filter: blur`), destoando do resto do sistema que é claro. Isso é exatamente o padrão "blue/teal AI gradient" que o SKILL.md recomenda remover — e aqui está presente nas duas "páginas de entrada". | 🟠 Alta |
| **Contraste / acessibilidade de cor** | Badges usam `--badge-*-bg` pastel + `--badge-*-fg` escuro, com comentário "WCAG AA" — boa prática já aplicada em `style.css`. | 🟢 Boa |
| **Espaçamento** | `padding: 24px 32px` (portal), `16px` (cards admin). Consistente, mas sem uma "escala de espaçamento" definida. | 🟡 Média |
| **Sombra** | `--shadow-sm/md` genéricos (pretos a baixa opacidade), não tintados. | 🟡 Média |
| **Layout responsivo** | `@media` em `portal_aluno.css` e `dashboard.html`. Grid `auto-fit` em resumos, grid 2-col em gráficos. Boa base responsiva. | 🟢 Boa |

### 1.4 Interatividade e estados (UI)

| Aspecto | Estado | Severidade |
|:---|:---|:---|
| **Hover/active** | `.nav-toggle:hover`, `.aula-card:hover`, `.portal-sidebar__item:hover` existem. Mas a maioria dos `.btn` admin e tabelas não tem estados de hover/active/pressed definidos no core. | 🟡 Média |
| **Focus ring** | Login tem `:focus` com `box-shadow` + `outline:none` (bom, mas remove outline nativo). O restante do sistema **não tem `:focus-visible`** padrão — crítico para acessibilidade por teclado. | 🟠 Alta |
| **Loading states** | Apenas `.aula-player-loading` no portal. Sem skeleton loaders para tabelas/relatórios do admin (que são densos e podem demorar). | 🟡 Média |
| **Empty states** | `ficha_aluno.html` tem bom tratamento de estados com badges/accordions. Mas listagens do admin (cursos, alunos, despesas, mensalidades) **não têm "estado vazio" composto** — exibem tabela vazia em branco. | 🟠 Alta |
| **Error/validação inline** | Flash messages (`get_flashed_messages`) usadas no server-side. Sem validação inline client-side nos formulários (ex.: `cadastro.js` lida com máscaras, mas não com mensagens de erro inline por campo). | 🟡 Média |
| **Navegação por `onclick=`** | `home.html` usa `onclick="location.href=..."` em cards; `financeiro.html` usa `onclick` em `<li>` do autocomplete. Link real com `<a href>` seria melhor para acessibilidade e SEO. | 🟡 Média |
| **Semântica HTML** | `base.html` usa `<header>`, `<nav>`, `<main>` corretamente. Mas muitos cards/divs são `div soup` (`.home-card`, `.curso-card`), sem `<article>`/`<section>` onde faria sentido. | 🟡 Média |

### 1.5 Acessibilidade (estado de fato)

| Aspecto | Estado | Severidade |
|:---|:---|:---|
| **ARIA** | `aria-label`, `aria-expanded`, `aria-hidden` presentes em apenas **4 de 46 templates** (`base`, `home`, `ficha_aluno`, `atividades_entregas`). | 🟠 Alta |
| **`<label for>`** | Usado no login (`for="login"`, `for="senha"`). Muitos campos em outros templates usam `<label class="campo">` sem `for`/`id`. | 🟡 Média |
| **`lang`** | `base.html` tem `<html lang="pt-br">` ✅; `login.html` também. | 🟢 Boa |
| **Skip link** | **Ausente.** Sem "pular para conteúdo" para navegação por teclado. | 🟠 Alta |
| **`alt` de imagens** | Logo tem `alt="Logo CQP"`. `dashboard.html` usa canvas (gráficos) sem fallback de texto. | 🟡 Média |
| **Contraste** | Badges AA ✅; gradiente escuro no login/home tem texto branco sobre azul — aceitável, mas o restante é claro. | 🟢 Boa |

---

## 2. Prós de reestilizar segundo o SKILL.md (o que VALE para este sistema)

1. **Trocar Arial por fonte com caráter** — melhor leitura em tabelas densas. (Geist, Satoshi, Outfit para UI; corpo legível.)
2. **Ativar `font-variant-numeric: tabular-nums`** — **é o maior ganho** para um painel financeiro: colunas de R$ e notas alinham verticalmente.
3. **Escala tipográfica** (H1–H4 com pesos 500/600) — hierarquia clara em `ficha_aluno`, boletim, dashboard.
4. **Estados interativos** — hover/active/`focus-visible` consistentes em todos os botões e linhas de tabela (acessibilidade + percepção de qualidade).
5. **Estados vazios/loading/erro** — dashboards com "sem dados" composto em vez de tabela em branco.
6. **Consistência visual** — remover o gradiente escuro do login/home (o único ponto "AI fingerprint") e alinhar ao restante claro.
7. **Sombra tintada + raios variados** — profundidade sutil e consistente.

## 3. Contras de reestilizar segundo o SKILL.md (o que NÃO se aplica)

1. **44 regras do SKILL.md são irrelevantes** — o sistema é **interno** (gestão/LMS), não landing page. Hero `100vh`, pricing 3 colunas, testimonials carousel, footer 4 colunas, cookie consent, parallax, scroll-driven reveals **não têm lugar aqui**.
2. **Risco altíssimo de quebra funcional** — 46 templates ligados a rotas Flask com POST, CSRF, savepoints, correção de provas/exercícios. Reestilização em massa é caminho direto para bugs no portal do aluno, provas e exercícios.
3. **"Não reescrever do zero" é regra**, mas muitas técnicas (glassmorphism, mesh gradients, motion spring) são **anti-ergonômicas** em um sistema de escritório denso.
4. **Jinja2 server-rendered ≠ componentes reaproveitáveis** — cada melhoria de componente precisa ser refeita por template; não há um design system compartilhado entre 46 arquivos.
5. **Custo alto vs. retorno** — o backend (DT-09, DT-03, DT-22) tem prioridade de manutenibilidade muito maior que o CSS.

---

## 4. Verditо

**O frontend tem uma base sólida** (variáveis CSS, nomes BEM, badges AA, responsivo, contraste de badges bem pensado). Ele foi **recentemente melhorado** (ficha_aluno com accordions + badges de status, commits recentes de "style/feat ficha").

**Os 3 maiores problemas reais do frontend são:**
1. **Acessibilidade** — sem skip-link, sem `focus-visible` global, ARIA em só 4/46 templates. (Alta severidade, baixo custo de correção.)
2. **Tipografia financeira** — Arial + números proporcionais em tabelas de R$ (perde alinhamento). (Médio custo, alto ganho percebido.)
3. **Estados vazios/loading/erro** — dashboards densos sem tratamento "vazio". (Médio custo.)

**Recomendo NÃO aplicar o SKILL.md integralmente.** Aplicar como **checklist de filtros** — pegando apenas tipografia, `tabular-nums`, estados de interação e estados vazios/erro. **Ignorar** regras de marketing (hero, pricing, testimonials, parallax, glassmorphism).

---

## 5. Plano de ciclos sugerido (melhoria incremental, por commit)

> Princípio: **verificar após cada mudança**, prioridade por impacto visual / risco mínimo (alinhado ao "Fix Priority" do SKILL.md, adaptado para dashboard interno).

| Ciclo | Foco | Escopo | Risco | Esforço LLM |
|:---|:---|:---|:---|:---|
| **C1** | **Tipografia + números** | definir escala tipográfica, trocar Arial por fonte com caráter, ativar `tabular-nums` em tabelas de R$/notas. Alterar `:root` em `style.css`, não os 46 templates | 🟢 Baixo | ~40 min |
| **C2** | **Acessibilidade** | adicionar skip-link em `base.html`, `:focus-visible` global, `aria-expanded` no hambúrguer (já tem), `label for` nos campos órfãos | 🟢 Baixo | ~50 min |
| **C3** | **Estados interativos** | hover/active em todos os `.btn`, linhas de tabela, `:focus-visible`. Centralizar transições | 🟢 Baixo | ~40 min |
| **C4** | **Estados vazios/loading/erro** | componentes reutilizáveis em Jinja2 (macro `empty_state`, `skeleton_table`), aplicar nas listagens do admin | 🟡 Médio | ~60 min |
| **C5** | **Limpeza de CSS inline** | extrair `<style>` duplicado de `provas.html`/`exercicio_questoes.html` para o core; substituir `!important` e cores hardcoded por variáveis | 🟡 Médio | ~60 min |
| **C6** | **Consistência de cor** | remover gradiente escuro do login/home; alinhar ao restante claro; sombras tintadas | 🟡 Médio | ~40 min |

**Estimativa total (LLM como agente):** ~3,5–5 horas de trabalho ativo para os ciclos C1–C6. Cada ciclo é um commit Conventional Commits isolado (igual foi feito na v5 do `SYSTEM_CONTEXT.md`).

**Prioridade recomendada:** **C1 (tipografia financeira)** e **C2 (acessibilidade)** primeiro — maior impacto percebido, menor risco. **Evitar** C6 (consistência de cor no login) até C1–C2, pois mexer no gradiente é isolado mas menos crítico.

---

## 6. Critérios para priorizar manutenibilidade (frontend vs backend)

| Prioridade | Área | Justificativa | Facilidade |
|:---|:---|:---|:---|
| 🥇 | Backend DT-09 (RBAC) | risco de segurança/compliance | Médio |
| 🥈 | Backend DT-03 / DT-22 | divergência de comportamento / 500 em input | Baixo |
| 🥉 | Frontend C1 (tipografia) | alto ganho percebido, baixo risco | Baixo |
| 4º | Frontend C2 (acessibilidade) | requisito, baixo custo | Baixo |
| 5º | Frontend C3–C6 | polimento | Médio |

> **Nota:** o frontend entrega mais "polimento percebido", mas o backend concentra a **dívida técnica de risco** (corrupção de dado, segurança, 500). Sugere-se primeiro resolver DT-09/DT-03/DT-22 e depois aplicar CI–C6.
