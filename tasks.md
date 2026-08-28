# Plano de Voo — Refatoração Cirúrgica

Plano dividido em **Ondas de Impacto**, derivado das 22 Dívidas Técnicas do
`SYSTEM_CONTEXT_v5.md`. Cada onda deve ser concluída, testada e commitada
antes do início da próxima.

Regras:
- Nenhuma task altera comportamento visível ao usuário, exceto onde marcado **CRÍTICO**.
- Tasks marcadas `(extra)` não pertencem à DT da seção; são achados da auditoria de código.
- Onda 4 é **implementação greenfield**: nenhuma referência ao Asaas existe no repositório.

---

## Onda 0 — Correção Crítica Pendente
**Foco:** DT-02 — única dívida crítica ainda aberta no `SYSTEM_CONTEXT_v5.md`

- [ ] **CRÍTICO — corrigir status de frequência no PDF**
  Arquivos: `services/pdf_service.py` (`gerar_historico_frequencia`), `enums.py`.
  Objetivo: a linha `txt = "Presente" if h.status == "P" else "Falta"` compara com `"P"`, mas o sistema grava `"Presente"` (`StatusFrequencia.PRESENTE`). **Todo aluno presente aparece como falta no histórico em PDF.** Comparar contra `StatusFrequencia.PRESENTE.value` e tratar `"Justificada"` como terceiro caso. O mesmo bug já foi corrigido em `frequencia_service.calcular_percentual`.

---

## Onda 1 — Limpeza de Código e Unificação
**Foco:** DT-03 (`_calcular_nota` duplicada em 3 rotas), DT-20 (`aluno.py` duplica lógica de matrícula), DT-15 (lógica de exercícios duplicada entre portal e admin)

### DT-03 — Unificar `_calcular_nota`

- [ ] **Centralizar `_calcular_nota` em `services/notas_service.py`**
  Arquivos: `services/notas_service.py`, `routes/provas.py`, `routes/provas_aluno.py`, `routes/exercicios.py`, `routes/portal_aluno.py`.
  Objetivo: existem 3 cópias locais (`provas.py:9`, `provas_aluno.py:66`, `exercicios.py:31`) mais um wrapper redundante em `portal_aluno.py`. Todas passam a importar `calcular_nota_escala` do serviço; remover as 4 definições locais. **Preservar** o comportamento de `exercicios.py`, que decide aprovação por pontos brutos via `_pontos_minimo_aprovacao()`, não pela nota 0–10.

### DT-20 — Unificar lógica de matrícula em `aluno.py`

- [ ] **CRÍTICO — resolver rota duplicada `/matricula/<int:matricula_id>/status`**
  Arquivos: `routes/aluno.py` (`atualizar_status_matricula`), `routes/financeiro.py` (`alterar_status_matricula`), `app.py`.
  Objetivo: as duas rotas registram a **mesma URL com o mesmo método POST**. Como `aluno_bp` é registrado antes de `financeiro_bp` em `app.py`, vence a versão de `aluno.py` — e a de `financeiro.py`, única que sincroniza `Aluno.status` via `_sincronizar_status_aluno`, é **código morto**. Manter a implementação de `financeiro.py` e remover a de `aluno.py`.

- [ ] **Fazer `matricular_aluno` usar `matricula_service`**
  Arquivos: `routes/aluno.py`, `services/matricula_service.py`.
  Objetivo: a rota cria `Matricula(status="ATIVA")` com string literal, sem passar por `normalizar_status`. Delegar ao serviço, expondo se necessário uma função `criar_matricula_simples(aluno_id, curso_id)` para o caso sem parcelas.

- [ ] **Alinhar `status_validos` ao enum**
  Arquivos: `routes/aluno.py`, `enums.py`.
  Objetivo: `atualizar_status_matricula` aceita `"PRE_MATRICULA"`, valor **inexistente** em `StatusMatricula` — `normalizar_status` o rebaixaria silenciosamente para `ATIVA`. Decidir entre adicionar o membro ao enum ou removê-lo da whitelist, e passar a consumir `StatusMatricula.valores()`.

### DT-15 — Centralizar lógica de exercícios

- [ ] **Criar `services/exercicio_service.py`**
  Arquivos: `services/exercicio_service.py` (novo), `routes/portal_aluno.py`, `routes/exercicios.py`.
  Objetivo: `responder_exercicio` (portal) e `corrigir_tentativa_exercicio` / `_recalcular_tentativas_sem_nota` (admin) recalculam pontos e aprovação com regras divergentes — o portal calcula `pontos_minimos` inline, o admin usa `_pontos_minimo_aprovacao()`. Extrair `calcular_resultado_tentativa()` e `pontos_minimos_aprovacao()` como fonte única.

- [ ] **Unificar validação de tentativas e tempo limite**
  Arquivos: `services/exercicio_service.py`, `routes/portal_aluno.py`, `routes/exercicios.py`.
  Objetivo: mover `max_tent = (ex.tentativas or 1) + (lib.extra_tentativas or 0)` (duplicado em `realizar_exercicio` e `responder_exercicio`) e a checagem de `tempo_limite` para o serviço, **preservando o savepoint aninhado** que mitiga o BUG-5.

### Limpeza geral (extra)

- [ ] **Criar `utils/formatters.py` com `cpf_limpo()`**
  Arquivos: `utils/formatters.py` (novo), `routes/aluno.py`, `routes/admin_utils.py`, `routes/portal_aluno.py`.
  Objetivo: três implementações divergentes — `aluno.py` usa `.replace()` em cadeia, `admin_utils.py` usa `re.sub(r"\D", "")`, e `portal_aluno._buscar_aluno_por_login` repete o `re.sub` inline. Adotar a versão regex como canônica.

- [ ] **Criar `services/curso_service.py` com `listar_tipos_curso()`**
  Arquivos: `services/curso_service.py` (novo), `routes/academico.py`, `routes/financeiro.py`, `routes/cursos.py`.
  Objetivo: unificar `_tipos_curso()` (duplicado em `academico.py` e `financeiro.py`) e a mesma query `distinct(Curso.tipo)` repetida inline em `cursos.listar_cursos`.

- [ ] **Criar `utils/sessao.py` com `operador_atual()`**
  Arquivos: `utils/sessao.py` (novo), `routes/atividades.py`, `routes/liberacoes.py`, `routes/provas.py`, `routes/exercicios.py`, `routes/aluno.py`.
  Objetivo: as chaves lidas divergem por arquivo — `atividades.py` lê `usuario`/`nome`; `liberacoes.py` lê `usuario_nome`/`usuario`/`nome`; `provas.py` e `exercicios.py` leem `session.get("usuario", "")`; `aluno.py` consulta o `Usuario` no banco para obter `admin_nome`. Padronizar em `usuario_nome` → `usuario` → `"sistema"`.

- [ ] **Mover `_sincronizar_status_aluno` para o serviço**
  Arquivos: `services/matricula_service.py`, `routes/financeiro.py`.
  Objetivo: tirar regra de negócio da rota; `alterar_status_matricula` passa a chamar `matricula_service.sincronizar_status_aluno(aluno)`. Mover também `_MATRICULA_PARA_ALUNO` e o dicionário de labels para `enums.py` como `StatusMatricula.para_status_aluno()` e `StatusMatricula.label()`.

- [ ] **Unificar helpers de matrícula ativa**
  Arquivos: `routes/portal_aluno.py`, `services/matricula_service.py`.
  Objetivo: `_matriculas_ativas()` e `_matricula_ativa()` duplicam `get_matricula_ativa()` do serviço; expor `listar_matriculas_ativas()` e migrar as ~8 chamadas do portal.

- [ ] **Corrigir assinatura inconsistente de `gerar_declaracao_matricula`**
  Arquivos: `routes/academico.py`, `routes/portal_aluno.py`, `services/pdf_service.py`.
  Objetivo: **bug confirmado** — `pdf_service.gerar_declaracao_matricula(aluno, matricula, curso, root_path="")` exige `curso` posicional, mas `academico.declaracao_matricula_pdf` e `portal_aluno.minha_declaracao_matricula` chamam sem ele → `TypeError` em runtime. Somente `aluno.declaracao_matricula_pdf` passa os 3 argumentos. Corrigir os dois chamadores.

- [ ] **Extrair modal de senha do JS**
  Arquivos: `static/js/financeiro.js`, `static/js/modal_senha.js` (novo), `templates/financeiro.html`.
  Objetivo: isolar `confirmarExclusao` / `confirmarSenha` / `fecharModalSenha` em módulo reutilizável, removendo a variável global `formAtual`. Atenção: `static/js/cadastro.js` já tem uma função homônima `confirmarExclusao` com assinatura diferente — evitar colisão de nomes no escopo global.

- [ ] **Substituir literais de status por enums**
  Arquivos: `routes/financeiro.py`, `enums.py`.
  Objetivo: trocar `"Pendente"`/`"Pago"` por `StatusMensalidade.*.value` (rotas `financeiro`, `pagar`); `Aluno.status.in_(["Ativo", "Pré-Matrícula"])` por `StatusAluno.ATIVO`/`StatusAluno.PRE_MATRICULA` (rotas `movimentacao`, `lancar_mensalidade` — ambos os membros já existem em `enums.py`); e `db.func.upper(Matricula.status) == "ATIVA"` por `StatusMatricula.ATIVA.value` (`lancar_mensalidade`, `api_cursos_ativos_aluno`).

- [ ] **Substituir literais de status em `services/matricula_service.py`**
  Arquivos: `services/matricula_service.py`, `enums.py`.
  Objetivo: os 3 blocos de criação de `Mensalidade` usam `status="Pendente"` literal; trocar por `StatusMensalidade.PENDENTE.value`. Definir também a constante `FLAG_APENAS_MENSALIDADE = "1"` para o par produtor/consumidor de `apenas_mensalidade` (`financeiro.lancar_mensalidade` ↔ serviço).

- [ ] **Migrar API legada do SQLAlchemy para 2.0**
  Arquivos: `routes/financeiro.py`, `routes/funcionario.py`, `routes/cursos.py`, `routes/academico.py`, `routes/aluno.py`, `services/matricula_service.py`.
  Objetivo: substituir `Model.query.get()` / `Model.query.get_or_404()` por `db.session.get(Model, id)` / `db.get_or_404(Model, id)`, eliminando os `LegacyAPIWarning`. Pontos de maior densidade: `financeiro.py` (`pagar`, `editar_parcela`, `excluir_parcela`, `recibo`, `carne`, além de `Usuario.query.get(session["usuario_id"])` e `Curso.query.get`), `funcionario.py` (4 ocorrências), `academico.py` (uso massivo), `matricula_service.py` (`Aluno.query.get`, `Curso.query.get`).

- [ ] **Remover `.copy().to_dict()` redundante**
  Arquivos: `routes/financeiro.py` (`lancar_mensalidade`).
  Objetivo: usar `request.form.to_dict()` direto, sem o `.copy()` intermediário.

---

## Onda 2 — Blindagem Financeira e Validação
**Foco:** DT-22 (`float()`/`int()` sem `try/except` → HTTP 500), DT-05 (arredondamento de parcelas de material), DT-04 (mensagem de erro de data contraditória)

### DT-22 — Validar entrada numérica

- [ ] **Blindar conversões em `routes/cursos.py`**
  Arquivos: `routes/cursos.py`.
  Objetivo: `float(f.get("valor_mensal") or 0)`, `float(f.get("valor_matricula") or 0)` e `int(f.get("parcelas") or 1)` em `salvar_curso` e `editar_curso` lançam `ValueError` com input não numérico → HTTP 500. Envolver em `try/except (ValueError, TypeError)` com `flash(..., "erro")`, seguindo o padrão já usado em `financeiro.editar_parcela`.

- [ ] **Blindar conversões em `routes/despesas.py`**
  Arquivos: `routes/despesas.py`.
  Objetivo: mesmo tratamento para `float(f.get("valor") or 0)` nas rotas de criação e de edição de despesa.

- [ ] **Criar `utils/parse.py` com `to_float()` e `to_int()`**
  Arquivos: `utils/parse.py` (novo), `routes/cursos.py`, `routes/despesas.py`, `routes/financeiro.py`.
  Objetivo: eliminar o `try/except` repetido; helpers que lançam `ErroNegocio` com mensagem amigável. Alinhar com `_get_float`/`_get_int` de `matricula_service.py`, que já implementam a mesma ideia.

### DT-05 — Corrigir arredondamento de parcelas

- [ ] **Corrigir perda de centavos no rateio do material**
  Arquivos: `services/matricula_service.py` (linha ~294).
  Objetivo: `round(valor_material / parcelas_material, 2)` por parcela faz a soma divergir do total (ex.: R$ 100,00 em 3x → R$ 99,99). Calcular o resíduo e somá-lo na última parcela.

### DT-04 — Corrigir mensagem de erro de data

- [ ] **Alinhar mensagem de `_validar_data` ao formato aceito**
  Arquivos: `services/matricula_service.py`.
  Objetivo: `_validar_data` faz `strptime(..., "%Y-%m-%d")` mas a mensagem de erro orienta `DD/MM/AAAA` — o usuário que segue a instrução falha. Corrigir o texto para `AAAA-MM-DD` **ou** aceitar ambos os formatos no parse.

- [ ] **Extrair `utils/datas.py` e reaproveitar**
  Arquivos: `utils/datas.py` (novo), `services/matricula_service.py`, `routes/financeiro.py`.
  Objetivo: tornar público como `validar_data_iso()`, junto de `parse_ano_mes()` — que unifica os dois blocos `try: ano = int(...[:4])` duplicados no serviço — e do `datetime.strptime` inline de `financeiro._vencida`.

### Blindagem adicional (extra)

- [ ] **Envolver escritas financeiras em `try/except` com rollback**
  Arquivos: `routes/financeiro.py` (`pagar`, `editar_parcela`, `excluir_parcela`, `alterar_status_matricula`).
  Objetivo: `try: ... db.session.commit() except SQLAlchemyError: db.session.rollback(); flash(...)`. Hoje um erro no commit deixa a sessão suja e propaga 500.

- [ ] **Padronizar retorno de erro de negócio**
  Arquivos: `services/erros.py` (novo), `services/matricula_service.py`, `routes/financeiro.py`.
  Objetivo: criar `ErroNegocio(ValueError)` para diferenciar erro de validação (mensagem ao usuário) de erro inesperado (log + mensagem genérica). Hoje `criar_matricula` empacota `Exception` em `ValueError`, indistinguível de erro de input.

- [ ] **Validar `forma_pagamento` e `data_pagamento` no registro de pagamento**
  Arquivos: `routes/financeiro.py` (`pagar`).
  Objetivo: hoje ambos são gravados sem qualquer validação. Rejeitar forma fora de whitelist e data em formato inválido ou futura, reutilizando `utils/datas.validar_data_iso()`.

- [ ] **Validar `vencimento` e `tipo` na edição de parcela**
  Arquivos: `routes/financeiro.py` (`editar_parcela`).
  Objetivo: só o `valor` é validado; adicionar validação de data e whitelist de tipo (`matricula`, `mensalidade`, `material`, `outros`).

- [ ] **Bloquear valores negativos em `pre_matricula_pdf`**
  Arquivos: `routes/financeiro.py` (`pre_matricula_pdf`).
  Objetivo: o `try/except (ValueError, TypeError)` existente aceita negativos. Rejeitar `taxa < 0`, `mensalidade < 0`, `parcelas < 1`, `val_mat < 0`, `parc_mat < 1`.

- [ ] **Bloquear valores negativos na criação de matrícula**
  Arquivos: `services/matricula_service.py`.
  Objetivo: `_get_float` aceita `-500`; adicionar validação explícita `< 0` para `valor_matricula`, `valor_mensalidade` e `valor_material`.

- [ ] **Parametrizar o dia de vencimento**
  Arquivos: `services/matricula_service.py`, `config.py`.
  Objetivo: remover o `"-10"` hardcoded nos dois loops de geração de parcelas; ler do form ou de `DIA_VENCIMENTO_PADRAO`, com clamp para meses curtos (dia 31 em fevereiro).

- [ ] **Exigir matrícula ATIVA no lançamento avulso**
  Arquivos: `services/matricula_service.py`.
  Objetivo: no ramo `apenas_mensalidade`, o `filter_by(aluno_id, curso_id).order_by(id.desc()).first()` pode retornar matrícula `INATIVA`/`TRANCADA`. Filtrar por `StatusMatricula.ATIVA`.

- [ ] **Impedir edição/exclusão de parcela já paga**
  Arquivos: `routes/financeiro.py` (`editar_parcela`, `excluir_parcela`).
  Objetivo: `pagar` já bloqueia repagamento, mas `editar_parcela` e `excluir_parcela` alteram parcela `Pago` sem restrição. Exigir perfil administrativo e registrar motivo.

- [ ] **Adicionar constraints de integridade no modelo**
  Arquivos: `models.py`, nova migração em `migrations/versions/`.
  Objetivo: `CheckConstraint("valor > 0")` em `Mensalidade` e índice composto `(aluno_id, status)`.

- [ ] **Criar trilha de auditoria financeira**
  Arquivos: `models.py` (`LogFinanceiro` novo), `routes/financeiro.py`, nova migração.
  Objetivo: registrar quem pagou / editou / excluiu parcela e alterou status de matrícula (usuário, timestamp, IP, valores antes/depois), no mesmo espírito de `ContratoAceite`.

- [ ] **Normalizar fallback de `Mensalidade.curso_id` nulo (DT-18)**
  Arquivos: `models.py`, `routes/portal_aluno.py`, `routes/financeiro.py`.
  Objetivo: `curso_id` é `nullable=True`; o portal faz fallback explícito para parcelas com `curso_id == None` e `financeiro()` exibe `"-"`. Decidir entre backfill por migração ou formalizar o fallback num único helper.

---

## Onda 3 — Segurança e Controle de Acesso/RBAC
**Foco:** DT-09 (RBAC fraco na maioria das rotas), DT-10 (PDFs expõem dados sensíveis sem controle de acesso no service), isolamento de rotas de alunos

### DT-09 — Unificar e endurecer os decoradores

- [ ] **Criar fábrica `perfil_required(*perfis)`**
  Arquivos: `security.py`.
  Objetivo: substituir a lógica quase idêntica de `login_required`, `financeiro_required` e `admin_required` por um único gerador, mantendo os nomes atuais como aliases finos sobre `PerfilUsuario`.

- [ ] **Aplicar `_is_ajax()` em todos os decoradores**
  Arquivos: `security.py`.
  Objetivo: hoje só `financeiro_required` responde JSON 401/403; `login_required` e `admin_required` devolvem redirect HTML para chamadas `fetch()` — quebra `cadastro.js` e `financeiro.js`.

- [ ] **Normalizar o perfil na sessão**
  Arquivos: `security.py`, `routes/auth.py`.
  Objetivo: eliminar a ambiguidade `admin` vs `administrador` (`PERFIS_VALIDOS` / `ADMIN_PERFIS` / `FINAN_PERFIS`) gravando o perfil já normalizado em minúsculas no login e comparando contra `PerfilUsuario`.

- [ ] **CRÍTICO — corrigir `PERFIS_ADMIN` em `routes/atividades.py`**
  Arquivos: `routes/atividades.py`.
  Objetivo: `PERFIS_ADMIN = {"ADMIN", "SECRETARIA", "INSTRUTOR"}` é comparado com `session["perfil"].upper()`, mas o perfil real gravado por `funcionario.py` é `administrador` → `"ADMINISTRADOR"` **não está no set** e o administrador recebe 403 em `arquivo_entrega`. Consumir `PerfilUsuario` via a fábrica `perfil_required`.

- [ ] **Proteger rotas financeiras com o decorador correto**
  Arquivos: `routes/financeiro.py`.
  Objetivo: todas as 12 rotas usam `@login_required`, permitindo que perfil `instrutor` registre pagamento, edite parcela e altere status de matrícula. Aplicar `@financeiro_required` no módulo e `@admin_required` em `excluir_parcela`.

- [ ] **Blindar acesso direto a `session["usuario_id"]`**
  Arquivos: `routes/financeiro.py` (`excluir_parcela`).
  Objetivo: substituir a indexação direta (risco de `KeyError` → 500) por `session.get()` com verificação, como já é feito em `aluno.excluir_aluno`.

- [ ] **Auditar cobertura de CSRF nos POSTs**
  Arquivos: `templates/financeiro.html`, `templates/base.html`.
  Objetivo: `base.html` já expõe `<meta name="csrf-token">` e injeta `csrf_token` em todos os forms não-GET via handler global de `submit` — os dois forms de `excluir_parcela` estão cobertos **desde que o JS execute**. Adicionar `{{ csrf_token() }}` explícito nos templates como defesa em profundidade e mapear formulários que dependem exclusivamente do injetor JS.

### DT-10 — Controle de acesso a PDFs com dados sensíveis

- [ ] **Auditar todos os chamadores de `pdf_service`**
  Arquivos: `services/pdf_service.py`, `routes/financeiro.py`, `routes/academico.py`, `routes/aluno.py`, `routes/portal_aluno.py`.
  Objetivo: o serviço gera CPF, RG, endereço, telefone e dados financeiros sem validar permissão — a autorização depende inteiramente do chamador. Mapear as 8 funções públicas e o decorador de cada rota que as invoca.

- [ ] **Restringir `gerar_contrato_assinado` a perfis administrativos**
  Arquivos: `routes/aluno.py` (`contrato_pdf`), `security.py`.
  Objetivo: a rota usa apenas `@login_required` e expõe CPF, RG, nascimento, e-mail, telefone, IP e user-agent do aluno. Exigir `@admin_required` ou perfil secretaria.

- [ ] **Restringir emissão de recibo e carnê**
  Arquivos: `routes/financeiro.py` (`recibo`, `carne`).
  Objetivo: ambas usam `@login_required` e aceitam qualquer `aluno_id`/`mensalidade_id`. Aplicar `@financeiro_required`.

- [ ] **Aplicar `garantir_dono` nas emissões do portal**
  Arquivos: `routes/portal_aluno.py`.
  Objetivo: `minha_declaracao_matricula` usa `session["aluno_id"]` (correto). Formalizar a regra para que qualquer nova rota de PDF no portal passe pela guarda de propriedade.

- [ ] **Avaliar marca d'água / rodapé de rastreio**
  Arquivos: `services/pdf_service.py`.
  Objetivo: incluir opcionalmente quem emitiu e quando, para rastrear vazamentos.

### Isolamento de rotas de alunos (extra)

- [ ] **Endurecer `aluno_login_required`**
  Arquivos: `security.py`.
  Objetivo: a condição `session.get("perfil") not in ("aluno", None)` aceita sessão sem perfil. Exigir `perfil == "aluno"` e revalidar que o aluno existe e não está em `_STATUS_BLOQUEADOS`.

- [ ] **Limpar sessão cruzada no login admin**
  Arquivos: `routes/auth.py`.
  Objetivo: `portal_aluno.login_aluno` já faz `session.clear()`, mas `auth.login` não — e `_vincular_aluno` grava `aluno_id` numa sessão que também tem `usuario_id`, permitindo coexistência dos dois portais.

- [ ] **Criar guarda de propriedade `garantir_dono(aluno_id)`**
  Arquivos: `security.py`, `routes/portal_aluno.py`, `routes/provas_aluno.py`.
  Objetivo: helper central que compara o `aluno_id` do recurso com o da sessão e retorna 403. `resultado_prova_aluno` e `resultado_exercicio` já fazem essa checagem inline — migrar para o helper.

- [ ] **Corrigir IDOR e path traversal em `download_entrega`**
  Arquivos: `routes/atividades.py`.
  Objetivo: a rota recebe `<path:filename>` livre e serve qualquer arquivo do `UPLOAD_FOLDER` a qualquer usuário logado, sem vincular o arquivo à entrega ou ao dono. O `os.path.basename()` mitiga traversal, mas não a enumeração. Restringir a perfis administrativos e validar o vínculo com `EntregaAtividade`.

- [ ] **Adicionar rate limit nas rotas sensíveis do portal**
  Arquivos: `routes/provas_aluno.py`, `routes/portal_aluno.py`.
  Objetivo: `login_aluno` e `auth.login` **já têm** `@limiter.limit("10 per minute")`. Aplicar limite em `realizar_prova` (POST), `responder_exercicio`, `entregar_atividade` e `csrf_token_atual` (heartbeat sem limite hoje).

---

## Onda 4 — O Motor do Pix Nativo
**Foco:** implementação nativa de cobrança Pix (ver Fase 4.0 antes de iniciar)

### Fase 4.0 — Levantamento

- [ ] **Confirmar ausência total do Asaas**
  Arquivos: varredura `grep -ri asaas` em todo o repositório.
  Objetivo: **nenhuma referência ao Asaas foi encontrada** em `requirements.txt`, `config.py`, `.env.example`, `app.py` ou nas rotas/serviços auditados. Confirmar contra o `SYSTEM_CONTEXT_v5.md`; se confirmado vazio, esta onda é **implementação greenfield** e a Fase 4.3 se limita a feature flag e testes.

- [ ] **Definir contrato do provedor de cobrança**
  Arquivos: `services/cobranca_base.py` (novo).
  Objetivo: interface abstrata (`criar_cobranca`, `consultar_status`, `cancelar`) para permitir troca de provedor sem alterar as rotas.

### Fase 4.1 — Núcleo Pix

- [ ] **Criar `utils/crc16.py`**
  Arquivos: `utils/crc16.py` (novo).
  Objetivo: implementar CRC16-CCITT-FALSE (polinômio `0x1021`, init `0xFFFF`), obrigatório no campo 63 do BR Code.

- [ ] **Criar `services/pix_service.py`**
  Arquivos: `services/pix_service.py` (novo).
  Objetivo: montar payload EMV do Pix estático/dinâmico — `montar_brcode(chave, nome, cidade, valor, txid)` com TLV (`id-len-value`), `gerar_txid(mensalidade_id)` e `gerar_qrcode_base64()`.

- [ ] **Adicionar configuração Pix**
  Arquivos: `config.py`, `.env.example`, `requirements.txt`.
  Objetivo: `PIX_CHAVE`, `PIX_NOME_RECEBEDOR`, `PIX_CIDADE`, `PIX_TXID_PREFIX`, com validação dos limites de tamanho do BR Code. Incluir `qrcode[pil]` em `requirements.txt` (dependência ausente hoje).

- [ ] **Criar modelo `CobrancaPix`**
  Arquivos: `models.py`, nova migração.
  Objetivo: colunas `mensalidade_id` (FK), `txid` (único), `valor`, `brcode`, `status`, `criado_em`, `pago_em`, `conciliado_por`.

### Fase 4.2 — Interface e conciliação

- [ ] **Criar `routes/pix.py`**
  Arquivos: `routes/pix.py` (novo), `app.py` (registro do blueprint).
  Objetivo: `GET /pix/<mensalidade_id>` (gera/recupera BR Code) e `POST /pix/<txid>/conciliar` (baixa manual sob `@financeiro_required`).

- [ ] **Criar template do QR Code**
  Arquivos: `templates/pix_qrcode.html` (novo), `templates/financeiro.html`.
  Objetivo: exibir QR Code e "Pix Copia e Cola" com botão de copiar; adicionar link na coluna de ações das parcelas pendentes.

- [ ] **Integrar baixa Pix ao fluxo de pagamento**
  Arquivos: `routes/financeiro.py` (`pagar`), `services/pix_service.py`.
  Objetivo: ao conciliar, gravar `forma_pagamento = "Pix"`, `status = StatusMensalidade.PAGO` e `usuario_pagamento`, reutilizando o caminho já auditado e com rollback da Onda 2.

- [ ] **Expor Pix no portal do aluno**
  Arquivos: `routes/portal_aluno.py`, `templates/aluno/financeiro.html`.
  Objetivo: aluno gera o BR Code apenas das próprias parcelas pendentes, protegido por `garantir_dono` (Onda 3).

### Fase 4.3 — Transição e testes

- [ ] **Feature flag de transição**
  Arquivos: `config.py`, `routes/pix.py`.
  Objetivo: `PROVEDOR_COBRANCA = "pix_nativo" | "manual"` para rollback imediato sem deploy.

- [ ] **Testes do motor Pix**
  Arquivos: `tests/test_pix_service.py` (novo).
  Objetivo: validar CRC16 contra BR Codes de referência, tamanho dos campos TLV, unicidade de `txid` e idempotência da conciliação.
