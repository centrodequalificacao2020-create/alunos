# SYSTEM_CONTEXT_v6.md
_Gerado na Sessão 5 — 26/08/2026 | Re-verificação completa por módulo (17 commits pós-v4, branch `feature/cloudinary-storage`)_
_Atualizado em 28/09/2026 — adiciona `EntradaCaixa` / `entradas_bp` (entradas manuais de caixa com exclusão lógica)._
_Atualizado em 26/10/2026 (Sessão 6) — **DT-02 corrigida e verificada**; módulo de certificados introduzido; suíte de testes criada._
_Atualizado em 26/10/2026 (Sessão 7) — **DT-23 resolvida**: tabela `certificados`, rotas de emissão/download/cancelamento e snapshot imutável. Renderer agora é determinístico (`invariant=1`), o que torna o `hash_sha256` verificável._

---

## 1. Visão Geral
* **O que o sistema faz:** Sistema integrado de gestão escolar e portal de aprendizado (LMS). Gerencia matrículas, controle financeiro (mensalidades e despesas), enturmação, lançamento de presenças e publicação de conteúdos didáticos, além de oferecer um ambiente para que estudantes realizem provas, exercícios e entreguem atividades acadêmicas. Inclui sistema de contrato digital com aceite eletrônico (SHA-256 + log imutável).
* **Público-alvo:** Administradores escolares (secretaria, financeiro, instrutores) e alunos matriculados nos cursos oferecidos.
* **Status atual:** Sistema legado — em processo de auditoria para modernização e conversão SaaS. Vários bugs críticos já corrigidos desde a v3.

---

## 2. Stack Técnico
* **Framework e versão:** Flask `3.0.3` com proteção CSRF via Flask-WTF `1.2.2`.
* **Banco de dados:** SQLite local (`cqp.db`) via SQLAlchemy `2.0.36` + Flask-SQLAlchemy `3.1.1`. Migrações via Flask-Migrate `4.0.7`.
* **Bibliotecas críticas:**
  * `gunicorn==22.0.0` — servidor WSGI para deploy
  * `Flask-Limiter==3.8.0` — rate limiting
  * `reportlab==4.2.2` — geração de PDFs
  * `python-dateutil==2.9.0` — manipulação de datas
  * `python-dotenv==1.0.1` — variáveis de ambiente
  * `Werkzeug==3.0.3` — hashing de senha e utilitários WSGI
  * `cloudinary>=1.36.0` — storage externo de arquivos (PDFs, imagens) ⚠️ pinado como `>=` (mínimo), não exato como os demais
  * `requests>=2.31.0` ⭐ NOVO — usado no proxy de arquivos Cloudinary (`file_service.py`)
* **Deploy:** Gunicorn em ambiente Unix/Linux (PythonAnywhere). Sem CI/CD identificado no código.
* **Storage:** Cloudinary para uploads (conteúdos, exercícios, atividades). Fallback para arquivos locais em `static/uploads/`.

---

## 3. Entidades do Domínio

### `Usuario`
* Contas administrativas e docentes. Campos: `usuario` (único), `senha` (hash), `perfil`, `nome`, `cpf`, `data_nascimento`, `status`, `telefone`, `email`, `endereco`.

### `Curso`
* Cursos acadêmicos. Campos: `nome`, `valor_mensal`, `valor_matricula`, `valor_total`, `parcelas`, `tipo`, `duracao`.
* Relacionamentos: → `Aluno`, `Matricula`, `Materia`, `Turma`.

### `Turma` / `TurmaAluno`
* Agrupamento de alunos por curso/modalidade. `TurmaAluno` é tabela de junção com unique constraint em `(turma_id, aluno_id)`.

### `Aluno`
* Dados cadastrais, credenciais e acadêmicos. Campos: `nome`, `cpf`, `rg`, `status` (padrão 'Ativo'), `senha` (hash), `email`, `whatsapp`, `telefone_contato`, `endereco`, `complemento`, `bairro`, `cidade`, `estado`, `cep`, `responsavel_nome`, `responsavel_cpf`, `responsavel_telefone`, `responsavel_parentesco`.
* **Novos campos (pós-v3):** `contrato_assinado` (Boolean, nullable — NULL = isento, False = pendente, True = assinado), `contrato_assinado_em` (String(19)).
* Relacionamentos: → `Mensalidade`, `Matricula`, `Frequencia`, `Nota`, `LoginHistoricoAluno`, `RespostaExercicio`, `ContratoAceite`.

### `ContratoAceite` ⭐ NOVO
* Log imutável de aceite de contrato digital. Uma linha por aceite — nunca atualizada, apenas inserida.
* Campos: `aluno_id`, `versao`, `hash_contrato` (SHA-256 hex), `aceito_em`, `ip`, `user_agent`.
* Índices: `(aluno_id)`, `(aceito_em)`.

### `Matricula`
* Vínculo financeiro aluno↔curso. Campos: `status` (enum), `valor_matricula`, `valor_mensalidade`, `quantidade_parcelas`, `material_didatico`, `valor_material`, `observacao`, `data_matricula`, `data_cadastro`, `tipo_curso`.

### `Mensalidade`
* Cobranças periódicas. Campos: `valor`, `vencimento` (String), `status` (Pendente/Pago/Atrasado/Cancelado), `tipo` (matricula/mensalidade/material/outros), `parcela_ref`, `data_pagamento`, `forma_pagamento`, `usuario_pagamento`, `curso_id`.
* Índices: `(aluno_id)`, `(vencimento)`, `(status)`.

### `Frequencia`
* Presença diária. Campos: `data` (String), `status` (Presente/Falta/Justificada).
* Unique constraint: `(aluno_id, curso_id, data)`.

### `Materia` / `CursoMateria`
* Disciplinas dos cursos. `CursoMateria` é tabela N:N entre `Curso` e `Materia` com unique constraint.
* Relacionamentos: → `Conteudo`, `Nota`, `Exercicio`.

### `Conteudo`
* Aulas/apostilas de uma matéria. Campos: `titulo`, `arquivo` (URL), `arquivo_public_id` ⭐ NOVO (Cloudinary), `video`, `modulo`, `data`.

### `ProgressoAula`
* Conclusão individual de conteúdo por aluno. Campos: `aluno_id`, `conteudo_id`, `concluido`.

### `Nota`
* Nota definitiva do aluno no boletim. Campos: `nota` (Float), `resultado` (Aprovado/Reprovado/Cursando), `publicada`.
* Unique constraint: `(aluno_id, materia_id, curso_id)`.

### Tabelas de Liberação Granular
* `AcessoConteudoCurso` — libera acesso ao conteúdo completo de um curso para um aluno. Unique: `(aluno_id, curso_id)`.
* `MateriaLiberada` — libera matéria específica para aluno em um curso. Unique: `(aluno_id, materia_id, curso_id)`.
* `ProvaLiberada` — libera prova + controla `extra_tentativas` por aluno. Unique: `(aluno_id, prova_id)`.
* `ExercicioLiberado` — libera exercício + controla `extra_tentativas` por aluno. Unique: `(aluno_id, exercicio_id)`.
* `AtividadeLiberada` ⭐ NOVO — libera atividade + controla `extra_tentativas` por aluno. Unique: `(aluno_id, atividade_id)`.

### `Prova` / `Questao` / `Alternativa`
* Exame oficial com tempo limite e nota mínima. Resultado incide no boletim (`Nota`).
* Campos críticos em `Prova`: `tempo_limite` (minutos), `tentativas`, `nota_minima`, `ativa`.

### `RespostaProva` / `RespostaQuestao`
* Tentativa de prova: `tentativa_num`, `iniciado_em`, `finalizado_em`, `nota_obtida`, `aprovado`.

### `Exercicio` / `ExercicioQuestao` / `ExercicioAlternativa`
* Avaliações rápidas de fixação, resultado imediato, **não** incide no boletim oficial.
* Campos críticos: `nota_minima`, `tempo_limite`, `tentativas`, `arquivo`, `arquivo_public_id` ⭐ NOVO.

### `RespostaExercicio` / `RespostaExercicioQuestao`
* Tentativa de exercício: `tentativa_num`, `acertos`, `nota_obtida`, `aprovado`, `pontos_obtidos_total` ⭐ NOVO.

### `Atividade` / `AtividadeQuestao` / `EntregaAtividade`
* Trabalhos com envio de arquivo. `EntregaAtividade` armazena até 3 arquivos + `nota` + `feedback`.

### `Despesa`
* Saídas de caixa. Campos: `valor`, `recorrente`, `dia_vencimento`, `data_inicio`, `data_fim`, `categoria`.

### `EntradaCaixa` ⭐ NOVO
* Entradas de caixa **manuais**, sem vínculo com aluno ou mensalidade (ex.: venda de apostila avulsa no balcão, taxa extra, recebimento diverso). É o espelho de `Despesa` no lado das entradas.
* Campos: `descricao`, `valor`, `data` (String `YYYY-MM-DD`), `forma` (Dinheiro/PIX/Cartão débito/Cartão crédito/Transferência/Outro), `categoria`, `observacao`, `criado_em`, `criado_por`, `cancelado`, `cancelado_em`, `cancelado_por`, `motivo_cancelamento`.
* Índices: `(data)`, `(cancelado)`.
* **Exclusão LÓGICA** (`cancelado=1`): o registro nunca é apagado, preservando o histórico contábil — em contraste com DT-06/DT-07, que são deleção física.

### `Certificado` ⭐ NOVO
* Certificado de conclusão emitido. **Snapshot imutável** do que foi impresso: `nome_aluno`, `cpf_aluno`, `nome_curso`, `carga_horaria`, `aproveitamento`, `data_inicio`, `data_fim`.
* Por que snapshot: o PDF é documento probatório. Se o aluno mudar de nome ou o curso for renomeado depois, o certificado já entregue precisa continuar provando o que foi emitido.
* Rastreabilidade: `codigo_verificacao` (10 chars, único, sem `O/0/I/1/L`), `hash_sha256` do PDF, `layout_id`, `arquivo_url`/`arquivo_public_id` (Cloudinary, opcional), `emitido_em`, `emitido_por`.
* **Exclusão LÓGICA** (`status=CANCELADO` + `cancelado_em/por/motivo`): o código de verificação permanece consultável como "cancelado" em vez de "inexistente".
* Índices: `(aluno_id)`, `(codigo_verificacao)` + unique constraint.

### `Relatorio`
* Metas mensais. Campos: `mes` (YYYY-MM, **unique**), `meta`, `realizado`, `matriculas`, `matriculas_venda`.

### `LoginHistoricoAluno`
* Auditoria de acessos: `aluno_id`, `login_em` (String), `ip`, `user_agent`.
* Índices: `(aluno_id)`, `(login_em)`.

---

## 4. Mapa de Módulos

| Blueprint | Arquivo | Prefixo | Responsabilidade |
|:---|:---|:---|:---|
| `auth_bp` | `routes/auth.py` | `/` | Login/logout admin |
| `cursos_bp` | `routes/cursos.py` | `/` | CRUD de cursos |
| `aluno_bp` | `routes/aluno.py` | `/` | Gestão de alunos (secretaria) |
| `financeiro_bp` | `routes/financeiro.py` | `/` | Mensalidades e pagamentos |
| `dashboard_bp` | `routes/dashboard.py` | `/` | Relatórios gerenciais |
| `despesas_bp` | `routes/despesas.py` | `/` | Fluxo de despesas |
| `entradas_bp` ⭐ | `routes/entradas_caixa.py` | `/` | Entradas de caixa manuais (listagem, criação, cancelamento lógico) |
| `funcionario_bp` | `routes/funcionario.py` | `/` | Gestão de funcionários |
| `conteudos_bp` | `routes/conteudos.py` | `/` | Upload de aulas e apostilas |
| `academico_bp` | `routes/academico.py` | `/` | Notas, frequências, diário, turmas |
| `backup_bp` | `routes/backup.py` | `/` | Backup do banco |
| `provas_bp` | `routes/provas.py` | `/` | CRUD de provas (admin) |
| `atividades_bp` | `routes/atividades.py` | `/` | CRUD de atividades (admin) |
| `liberacoes_bp` | `routes/liberacoes.py` | `/` | Painel de liberações manuais |
| `admin_utils_bp` | `routes/admin_utils.py` | `/` | Utilitários administrativos |
| `exercicios_bp` | `routes/exercicios.py` | `/` | Testes rápidos por disciplina |
| `portal_aluno_bp` | `routes/portal_aluno.py` | `/aluno` | Portal do aluno (notas, progresso, aulas, exercícios, contrato) |
| `provas_aluno_bp` | `routes/provas_aluno.py` | `/aluno` | Realização de provas pelo aluno |
| `contrato_admin_bp` ⭐ | `routes/contrato_admin.py` | `/admin` | Auditoria e reset de aceite de contrato |
| `certificados_bp` ⭐ | `routes/certificados.py` | `/` | Emissão, download e cancelamento de certificados de conclusão |

---

## 5. Mapa de Services

| Arquivo | Funções Públicas | Chamado por |
|:---|:---|:---|
| `matricula_service.py` | `criar_matricula`, `get_matricula_ativa`, `get_cursos_matriculados_ativos`, `normalizar_status` | `routes/financeiro.py` (só `criar_matricula`), `routes/portal_aluno.py`, `routes/academico.py`. **⚠️ `routes/aluno.py` NÃO usa este service** — duplica lógica de matrícula localmente (`matricular_aluno`, `atualizar_status_matricula`) |
| `pdf_service.py` | `gerar_recibo` ⭐, `gerar_carne`, `gerar_boletim_notas`, `gerar_historico_frequencia`, `gerar_declaracao_conclusao`, `gerar_pre_matricula`, `gerar_declaracao_matricula` ⭐, **`gerar_contrato_assinado`** ⭐ NOVO | `routes/financeiro.py`, `routes/academico.py`, `routes/portal_aluno.py`, `routes/aluno.py` |
| `notas_service.py` | `calcular_nota_escala` ⭐, `get_materias_do_curso`, `get_notas_map`, `get_boletim`, `salvar_notas`, `get_curso_ativo_do_aluno` | `routes/academico.py`, `routes/portal_aluno.py`, `pdf_service.py` |
| `frequencia_service.py` | `registrar_frequencia`, `get_historico`, `calcular_percentual`, `normalizar_status` ⭐, `is_presente` ⭐, `percentual_presenca` ⭐ | `routes/academico.py`, `routes/portal_aluno.py`, `pdf_service.py` |
| `certificado_service.py` ⭐ | `validar_emissao`, `emitir_certificado`, `cancelar_certificado`, `certificados_do_aluno`, `buscar_por_codigo`, `pdf_do_certificado`, `normalizar_cpf`, `gerar_codigo_verificacao` | `routes/certificados.py` |
| `certificado_pdf.py` ⭐ | `gerar_certificado`, `dados_de_matricula`, `quebrar_em_linhas`, `carregar_layout_padrao` | `services/certificado_service.py` |
| `certificado_layout.py` ⭐ | `carregar_layout` | `services/certificado_pdf.py` |
| `aluno_service.py` | `buscar_alunos`, `get_aluno_ou_404` | `routes/aluno.py`, `routes/portal_aluno.py` |
| `file_service.py` ⭐ | `build_pdf_response`, `serve_local_file`, `proxy_remote_file` | `routes/portal_aluno.py`, `routes/atividades.py` |
| `storage_service.py` ⭐ | `upload_arquivo`, `deletar_arquivo` | `routes/conteudos.py`, `routes/exercicios.py`. **⚠️ `routes/atividades.py` NÃO usa `storage_service`** — usa `file_service.proxy_remote_file`/`serve_local_file` |

---

## 6. Regras de Negócio Críticas

* **Exercícios vs Provas:** Exercícios são autoavaliação imediata — resultado NÃO atualiza o boletim (`Nota`). Provas são formais — resultado incide diretamente em `Nota` com status de aprovação baseado em `nota_minima`.
* **Liberação granular:** Acesso a matérias, provas, exercícios e atividades é controlado por 5 tabelas de liberação individuais, independente da matrícula estar ativa.
* **Tolerância de tempo em provas:** +30 segundos além do `tempo_limite` configurado para mitigar latência de rede.
* **Timeout com nota zero:** Se o tempo de envio exceder `tempo_limite + 30s`, a nota é forçada para `0.0` e o aluno é reprovado, independente das respostas.
* **Nota na escala 0–10:** `(pontos_obtidos / total_pontos) * 10`, arredondado em 2 casas. Se total de pontos ≤ 0, retorna `0.0`.
* **Questões dissertativas:** Nota e status `aprovado` ficam como `None` até correção manual pelo instrutor.
* **Assinatura HMAC em provas:** Provas com tempo limite geram token HMAC-SHA256 contendo timestamp de início e mapa de embaralhamento de alternativas, validado no POST para impedir fraudes.
* **Limite de upload:** **30 MB** (`MAX_CONTENT_LENGTH = 30 * 1024 * 1024` em `config.py:49` — o doc v4 dizia 50 MB). Excedido → HTTP 413 com resposta JSON ou página HTML com redirect automático em 4s.
* **Datas como String:** Todos os campos de data (`vencimento`, `data_cadastro`, `iniciado_em`, etc.) são `String(10)` ou `String(19)`. Ordenação e validação temporal são responsabilidade do código Python.
* **Frequência: `P`/`F`/`J` são os valores canônicos.** O formulário (`templates/frequencia.html:64`) envia códigos curtos; `enums.StatusFrequencia` define os rótulos por extenso; o model declara default `"Presente"` (divergência histórica). **Use sempre `frequencia_service.is_presente()` / `normalizar_status()` — nunca compare strings de status diretamente.** Os dados reais são 100% `P`/`F`; `Justificada` nunca foi gravada e não conta como presença.
* **`Curso` não tem carga horária** — apenas `duracao` (`String(60)`), vazia em 100% dos 45 cursos. A carga horária do certificado é informada na emissão e persistida como snapshot em `certificados.carga_horaria` (ver DT-23, resolvida).
* **Filtros customizados:** `moeda` (float → R$ formato brasileiro) e `nl2br` (quebras de linha com escape seguro via `markupsafe`, normalizando `<br>` literais).
* **Segurança de ambiente:** Sem `FLASK_SECRET_KEY` em produção → `RuntimeError` na inicialização. Em dev → chave temporária gerada com `secrets.token_hex(32)` + `warnings.warn`.
* **SQLite concorrência:** Configurado com `check_same_thread: False`, `timeout: 30s` e `PRAGMA foreign_keys=ON`.
* **Contrato digital:** Alunos com `contrato_assinado=False` (explícito, não NULL) são redirecionados para `/aluno/contrato`. Cada aceite gera registro imutável em `ContratoAceite` com SHA-256 do template. NULL = aluno pré-implantação (isento).
* **Sessão segura:** Cookies com `HttpOnly=True`, `SameSite=Lax`, `Secure` em produção. Expiração em **8 horas** (`PERMANENT_SESSION_LIFETIME = timedelta(hours=8)` em `config.py:64` — o doc v4 dizia 1h; justificativa no código: suportar provas longas). `WTF_CSRF_TIME_LIMIT = 8 * 3600` (o token CSRF foi renomeado/estendido no commit `f3923b7`).
* **Rate limiting:** Login de aluno limitado a 10/min via Flask-Limiter com storage em memória (`memory://`). **Também** o login do admin (`routes/auth.py:37`) tem `@limiter.limit("10 per minute")` — o doc v4 só citava o do aluno.
* **PDF.js compatível:** `file_service.py` serve PDFs com headers `Content-Disposition: inline`, `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` ⚠️ (doc v4 dizia só `no-store`; inclui `Pragma: no-cache`), `Accept-Ranges: bytes`.
* **Proxy Cloudinary robusto (5 estratégias):** `file_service.py:312-438` tenta, em ordem: `upload` assinado → `private` assinado → `authenticated` assinado → `private_download_url(private)` → `private_download_url(authenticated)`. Usa `requests.get` para baixar e re-servir. Gera URL assinada via `_cloudinary_signed_url`.
* **CSRF heartbeat para páginas longas:** `GET /aluno/csrf-token` (`portal_aluno.py:296`) renova o token/cookie CSRF em provas/exercícios/atividades longas (commit `f3923b7`).
* **Entradas manuais somam no card "Entradas":** `dashboard.py` calcula `entradas_total = recebido_mes (mensalidades Pagas) + entradas_manuais (EntradaCaixa não canceladas no mês)`. **`entradas_total` substituiu `recebido_mes` em todos os indicadores derivados** — `lucro_liquido`, `margem_lucro`, `receita_projetada`, `ticket_medio`, `receita_total`, `receita_media` e no gráfico `("Receita", entradas_total)`. Ou seja, uma entrada manual impacta EBITDA, margem, ticket médio e receita projetada.
* **Exclusão lógica de entradas:** `POST /entradas-caixa/<id>/cancelar` marca `cancelado=1` + `cancelado_em`/`cancelado_por`/`motivo_cancelamento`; o registro permanece no banco. Cancelar duas vezes retorna 400. Entradas canceladas são excluídas de todas as somas.
* **Validação de entrada manual:** `_validar()` exige descrição (≤200), valor numérico > 0 e ≤ R$ 1.000.000, data no formato `AAAA-MM-DD`; `forma` fora da lista cai em `"Outro"`. Erros voltam como flash + redirect para `/entradas-caixa`.
* **Lançamento de entradas é só pela página dedicada:** o card "Add. Caixa" do dashboard é um **link** para `/entradas-caixa` (não há modal). A página oferece formulário de lançamento, filtro por qualquer mês, categoria/observação/quem lançou e o cancelamento.
* **Certificado é snapshot, não view:** `emitir_certificado` copia nome, CPF, curso, carga horária, aproveitamento e datas para `certificados`. Renomear o aluno ou o curso depois **não** altera certificados já emitidos. Não existe edição — emitir errado significa cancelar e emitir outro.
* **Carga horária e aproveitamento são informados na emissão:** `Curso` não tem carga horária (`duracao` vazia em 45/45) e nenhuma matrícula `CONCLUIDA` tem nota publicada (DT-24). Ambos são validados (`1–10000` horas, `0–100%`) e persistidos como snapshot.
* **Renderer determinístico:** `gerar_certificado` usa `canvas.Canvas(..., invariant=1)`, que remove data de criação e ID aleatório do PDF. A mesma entrada gera sempre os mesmos bytes — por isso `hash_sha256` detecta adulteração e `pdf_do_certificado` reproduz o arquivo original.
* **Cancelamento de certificado é lógico:** `status=CANCELADO` + `cancelado_em/por/motivo`. O `codigo_verificacao` continua existindo para que a consulta pública responda "cancelado" em vez de "inexistente". Cancelar duas vezes → flash de erro. **Nada é apagado** — não há `DELETE` em nenhum caminho de certificado.
* **FKs de `certificados` usam `ON DELETE SET NULL`:** excluir aluno, matrícula ou curso não pode ser bloqueado por um certificado já emitido, nem apagar o registro probatório. O snapshot é autossuficiente — o certificado continua válido e auditável com `aluno_id`/`matricula_id`/`curso_id` nulos.
* **Migração `f7a8b9c0d1e2` reconstrói a tabela:** como `db.create_all()` roda em todo startup, a tabela `certificados` normalmente já existe quando a migração executa — criada pelo ORM, com FKs `NO ACTION`. A migração detecta isso e reconstrói a tabela preservando as linhas (SQLite não suporta `ALTER` de FK). Sem esse passo, excluir aluno/matrícula passaria a falhar com `FOREIGN KEY constraint failed`.
* **Upload ao Cloudinary é opcional:** sem `CLOUDINARY_CLOUD_NAME` configurado, `_tentar_upload` retorna cedo e o download re-renderiza o PDF a partir do snapshot. Falha de upload também não invalida a emissão (o snapshot já está no banco).
* **Vírgula decimal no certificado:** carga horária e aproveitamento são impressos em pt-BR (`92,5%`, não `92.5%`), tanto no PDF (`text_corpo`) quanto na tela (`aproveitamento_texto`).

---

## 7. Decisões Arquiteturais

* **Datas como String** — simplifica templates, mas delega toda lógica temporal ao Python.
* **SQLite local** — limitação crítica para SaaS; sem suporte real a writes concorrentes.
* **Duplo isolamento de sessão** — `@login_required` bloqueia alunos; `@aluno_login_required` bloqueia admin. Separação correta de portais.
* **RBAC parcial (adoção em expansão)** — `security.py` tem `admin_required` e `financeiro_required`. **`dashboard.py` atingiu RBAC total** (todas as 7 rotas usam `@financeiro_required`). `funcionario.py` (3 rotas) e `cursos.py` (`excluir_curso`) usam `@admin_required`. `contrato_admin.py` e `atividades.py` (`PERFIS_ADMIN`) validam perfil. Mas `conteudos.py`, `academico.py`, `provas.py`, `liberacoes.py` e as rotas de escrita de `cursos/aluno/financeiro/despesas` ainda usam apenas `@login_required`.
* **Sem multi-tenancy** — nenhuma query em services ou routes filtra por `tenant_id`. Toda a base de dados é global. Impede SaaS sem refatoração de arquitetura.
* **`_calcular_nota` parcialmente unificada** — `notas_service.py` tem `calcular_nota_escala` (canônica, `:6`). `portal_aluno.py` importa e wrappa (`:35`). Ainda com cópias locais: `provas_aluno.py:66`, `exercicios.py:31`, `provas.py:9`. Nº de linhas atualizado na v5.
* **Lógica de negócio duplicada entre services e routes** — cálculo de notas, parsing de datas e validação de tentativas estão implementados tanto nas routes quanto nos services de forma inconsistente.
* **Imagens servidas de path local** — `pdf_service.py` busca imagens (logo, assinaturas) via path do sistema de arquivos local. Incompatível com deploy multi-servidor ou storage em nuvem.
* **Storage híbrido Cloudinary + local** — Uploads novos vão para Cloudinary; arquivos antigos podem estar em `static/uploads/`. `file_service.py` abstrai a leitura (local + proxy remoto). **`proxy_remote_file` foi significativamente expandido** (commit `eacc3fc`): tenta 5 estratégias de URL assinada/private/authenticated; `_response_mimetype` (`:281`) previne servir DOCX/imagem como PDF por engano.

---

## 8. Módulos Já Auditados

| Módulo | Arquivo(s) | Status |
|:---|:---|:---|
| Bootstrap + modelos | `app.py`, `models.py`, `config.py`, `security.py`, `enums.py`, `requirements.txt`, `runtime.txt` | ✅ Sessão 1 |
| Todas as rotas (`/routes`) | `academico.py`, `admin_utils.py`, `aluno.py`, `atividades.py`, `auth.py`, `backup.py`, `conteudos.py`, `contrato_admin.py`, `cursos.py`, `dashboard.py`, `despesas.py`, `entradas_caixa.py` ⭐, `exercicios.py`, `financeiro.py`, `funcionario.py`, `liberacoes.py`, `portal_aluno.py`, `provas.py`, `provas_aluno.py` | ✅ Sessão 2 + Sessão 4 + **Sessão 5 (re-verificação)** |
| Services | `matricula_service.py`, `pdf_service.py`, `notas_service.py`, `frequencia_service.py`, `aluno_service.py`, `file_service.py`, `storage_service.py` | ✅ Sessão 3 + Sessão 4 + **Sessão 5 (re-verificação)** |

---

## 9. Bugs Corrigidos (v3 → v5)

| ID | Descrição | Status |
|:---|:---|:---|
| BUG-1 | `_calcular_nota` duplicada — `portal_aluno.py` agora importa `calcular_nota_escala` do service | ✅ Parcial — `provas_aluno.py`, `exercicios.py` e `provas.py` ainda têm cópias locais |
| BUG-2 | PDF.js headers ausentes — `file_service.py` provê `build_pdf_response` com headers corretos | ✅ Corrigido (v5: headers mais completos — `Cache-Control` estendido + `Pragma`) |
| BUG-3 | `calcular_percentual` verificava `"P"` em vez de `"Presente"` — `frequencia_service.py` corrigido (`calcular_percentual:53`) | ✅ Corrigido |
| BUG-4 | Matrícula duplicada sem proteção — `matricula_service.py` agora tem guarda de duplicidade | ✅ Corrigido |
| BUG-5 | Race condition em tentativas de exercício — `portal_aluno.py` usa savepoint aninhado | ✅ Mitigado |
| BUG-6 | Tempo limite não enforçado em exercícios — `portal_aluno.py` agora valida no backend | ✅ Corrigido |
| BUG-7 | HMAC ausente para provas sem tempo limite — `provas_aluno.py` agora gera token de ordem de alternativas | ✅ Corrigido |
| BUG-8 | Filtro `moeda` com formato incorreto — corrigido para padrão brasileiro R$ 1.234,56 | ✅ Corrigido |
| BUG-9 | Filtro `nl2br` não normalizava `<br>` literais do banco — corrigido | ✅ Corrigido |
| BUG-10 | Sessão sem expiração — adicionado `PERMANENT_SESSION_LIFETIME = 1h` | ✅ Corrigido |
| BUG-11 | Cookies de sessão sem flags de segurança — adicionado HttpOnly, SameSite, Secure. ⚠️ Sessão estendida para 8h em `config.py:64` (v4 dizia 1h) | ✅ Corrigido |
| BUG-12 | `salvar_notas` sem validação de range 0–10 — adicionada validação com ValueError | ✅ Corrigido |
| BUG-15 🆕 | `gerar_boletim_notas` ocultava nota 0.0 — `if n and n.nota` → `if n is not None and n.nota is not None` (`pdf_service.py:236`) | ✅ Corrigido (equivalente à DT-01) |
| BUG-13 | `registrar_frequencia` sem validação de data futura — adicionada | ✅ Corrigido |
| BUG-14 | `criar_matricula` sem rollback em erro — envolvido em try/except com rollback explícito | ✅ Corrigido |
| BUG-16 🆕 | **`calcular_percentual` retornava 0,0% para 100% dos alunos** — comparava `"Presente"`, mas o banco guarda `P`. Corrigido com `normalizar_status`/`is_presente` | ✅ Corrigido (v6) |
| BUG-17 🆕 | **`frequencia_historico.html` renderizava tabela vazia** — template lia `r.data_aula`, `r.presente`, `r.justificativa`, mas o model só tem `data` e `status`. Data em branco, todas as linhas "Falta" | ✅ Corrigido (v6) |

---

## 10. Dívidas Técnicas Conhecidas (v5)

### 🔴 Críticas (risco de corrupção de dados ou falha funcional)

| ID | Descrição | Local | Impacto |
|:---|:---|:---|:---|
| **DT-01** | ✅ **CORRIGIDA (v5)** — `if n and n.nota` → `if n is not None and n.nota is not None` (`pdf_service.py:236`). Nota 0.0 agora aparece no boletim | `services/pdf_service.py:236` | ~~Reprovação não documentada~~ — resolvida no commit `89c8ff2` |
| **DT-02** | ✅ **CORRIGIDA (v6)** — o diagnóstico anterior estava **invertido**. Os dados reais são `P`/`F` (1087 `P`, 265 `F`, **zero** `Presente`); quem estava errado era `calcular_percentual`, que comparava `"Presente"` e retornava **0,0% sempre**. O PDF (`pdf_service.py:267`) já comparava `"P"` corretamente. Agora ambos usam `frequencia_service.is_presente()` | `services/frequencia_service.py`, `services/pdf_service.py` | ~~Frequência sempre 0%~~ — resolvida |
| **DT-03** | **`_calcular_nota` ainda duplicada em 3 rotas** — `provas_aluno.py:66`, `exercicios.py:31`, `provas.py:9` têm suas próprias implementações. Apenas `portal_aluno.py` importa do service. | `routes/provas_aluno.py`, `routes/exercicios.py`, `routes/provas.py` | Divergência de comportamento entre módulos |
| **DT-04** | **Mensagem de erro de data contraditória** — `_validar_data` faz parse de `YYYY-MM-DD` (`:84`) mas a mensagem orienta `DD/MM/AAAA` (`:93`). Se o usuário seguir a mensagem, o parse falha. | `services/matricula_service.py:75-93` | Confusão do usuário, erros de cadastro |
| **DT-05** | **Arredondamento de parcelas de material sem ajuste da última** — `round(valor_material / parcelas_material, 2)` por parcela, sem compensar o saldo na última. Perda de centavos. | `services/matricula_service.py:294` | Perda financeira acumulada |
| **DT-06** | **Deleção física de questões de prova** — `excluir_prova` (`:104-152`) deleta `RespostaQuestao`, `RespostaProva`, **`ProvaLiberada`** (não citado no doc v4), `Alternativa`, `Questao` e `Prova` em cascata manual. Remove registros referenciados por respostas históricas. | `routes/provas.py:104-152` | Corrompe histórico de notas e tentativas |
| **DT-07** | **Deleção física de questões de exercício** — `cascade="all, delete-orphan"` em `Exercicio.questoes` e `ExercicioQuestao.alternativas`. Mesmo problema da DT-06. | `models.py` (relationships) | Corrompe histórico de respostas |

### 🟠 Altas (risco de inconsistência ou bugs intermitentes)

| ID | Descrição | Local | Impacto |
|:---|:---|:---|:---|
| **DT-08** | **Race condition em tentativas de prova** — `provas_aluno.py` faz check-then-act sem savepoint (diferente de exercícios que já usam). Duas requisições simultâneas podem exceder `tentativas`. | `routes/provas_aluno.py:190-200` | Aluno pode fazer mais tentativas que o permitido |
| **DT-09** | **RBAC fraco na maioria das rotas** — `@login_required` não valida `perfil`. Apenas `contrato_admin.py` e `security.py` (decorators `admin_required`/`financeiro_required`) fazem validação. Rotas como `academico.py`, `cursos.py`, `conteudos.py` etc. aceitam qualquer perfil. | Diversas routes | Qualquer funcionário acessa qualquer rota |
| **DT-10** | **PDFs expõem dados sensíveis sem controle de acesso no service** — `pdf_service.py` gera documentos com CPF, endereço, dados financeiros. O service não valida permissões — depende das rotas chamadoras. | `services/pdf_service.py` | Vazamento de dados se chamado incorretamente |
| **DT-11** | **N+1 queries no portal do aluno** — `curso_detalhe` faz queries individuais para provas, exercícios, atividades e progresso. Uso de `joinedload` apenas em `Atividade.questoes`. | `routes/portal_aluno.py:680-860` | Performance degradada com muitos alunos |
| **DT-12** | **SQLite sem proteção real contra concorrência** — Apesar do savepoint em exercícios, SQLite serializa todas as escritas. Sob carga, fila de locks cresce. ⚠️ `check_same_thread`/`timeout` estão em **`config.py`**, não `db.py`. O `db.py` só têm `PRAGMA foreign_keys=ON` (`db.py:9-12`). | `config.py` / `db.py` | Gargalo em produção multi-usuário |
| **DT-13** | **Limiter com storage em memória** — `Flask-Limiter` usa `storage_uri="memory://"`. Com múltiplos workers Gunicorn, cada um tem seu próprio contador. Rate limiting não é global. | `app.py:16` | Rate limiting ineficaz em produção |

### 🟡 Médias (débito técnico, manutenibilidade)

| ID | Descrição | Local | Impacto |
|:---|:---|:---|:---|
| **DT-14** | **Import circular de models dentro de funções** — `portal_aluno.py`, `provas_aluno.py`, `liberacoes.py` e outras routes importam models dentro das funções (`from models import ...`) para evitar circular imports. | Diversas routes | Código frágil, difícil de manter |
| **DT-15** | **Lógica de negócio de exercícios duplicada** — `portal_aluno.py` (aluno) e `exercicios.py` (admin) têm lógica similar de cálculo de nota, validação de tentativas e correção. | `routes/portal_aluno.py`, `routes/exercicios.py` | Divergência de comportamento |
| **DT-16** | **Tratamento de erro inconsistente** — Algumas rotas usam `try/except OperationalError`, outras `except Exception`, outras sem tratamento. Mensagens de erro vazam detalhes internos em alguns casos. | Diversas routes | UX inconsistente, vazamento de informação |
| **DT-17** | **Frequencia com fallback para `curso_id=None`** — `portal_aluno.py` busca frequências sem `curso_id` como fallback, indicando dados órfãos no banco. | `routes/portal_aluno.py:501-510` | Dados inconsistentes |
| **DT-18** | **Mensalidades com fallback para `curso_id=None`** — Mesmo padrão da DT-17 para mensalidades. | `routes/portal_aluno.py:461` | Dados inconsistentes |
| **DT-19** | **Templates não versionados junto com código** — Mudanças no contrato (`_VERSAO_CONTRATO = "v1.0"`) não têm mecanismo de versionamento automático. | `routes/portal_aluno.py:32` | Risco de disputa legal sem rastreabilidade |
| **DT-20** 🆕 | **`aluno.py` duplica lógica de matrícula** — `matricular_aluno` (:511) e `atualizar_status_matricula` (:546) manipulam `Matricula.status` diretamente, sem usar `matricula_service.normalizar_status`. O §5 afirmava que `aluno.py` chama o service, mas não usa. | `routes/aluno.py:511,546` | Divergência de comportamento financeiro |
| **DT-21** 🆕 | **`liberacoes.py` não controla `AcessoConteudoCurso` nem `extra_tentativas`** — O §3/§6 afirmava o painel de liberações gerencia as 5 tabelas e o campo `extra_tentativas`. O código só manipula `MateriaLiberada`, `ProvaLiberada`, `ExercicioLiberado`, `AtividadeLiberada` e grava apenas `liberado/liberado_por/liberado_em`. `AcessoConteudoCurso` é tratado só em `aluno.py`. | `routes/liberacoes.py` | Funcionalidade documentada não implementada no painel; `extra_tentativas` nunca é gravado |
| **DT-22** 🆕 | **Input de valores sem validação de tipo** — `float(f.get("valor_mensal") or 0)` e `int(f.get("parcelas") or 1)` em `cursos.py:29-30,125`; `float(f.get("valor") or 0)` em `despesas.py:40,66`, sem `try/except`. Input não numérico → `ValueError` → HTTP 500. | `routes/cursos.py`, `routes/despesas.py` | Falha de robustez; input inválido derruba a rota |
| ~~**DT-23**~~ ✅ | ~~**Certificado não persiste metadados**~~ — **Resolvida na Sessão 7.** Tabela `certificados` com snapshot imutável (nome, CPF, curso, carga horária, aproveitamento, datas), `codigo_verificacao` único, `hash_sha256` do PDF, `layout_id`, autor e timestamps. Rotas: `GET/POST /aluno/<id>/certificados`, `GET /certificados/<id>/pdf`, `POST /certificados/<id>/cancelar` (lógico). O renderer passou a usar `invariant=1`, então o hash é reproduzível e detecta adulteração. | `models.Certificado`, `services/certificado_service.py`, `routes/certificados.py` | ~~Emissão sem rastreabilidade~~ |
| **DT-24** 🆕🟡 | **Nenhuma matrícula concluída possui nota publicada** — 68 matrículas `CONCLUIDA`, **zero** com nota no mesmo curso; 423 notas com `publicada=0`. Não é possível derivar `aproveitamento` do banco. Consequência de BUG-15/DT-01 ou de notas nunca publicadas. | `cqp.db` / fluxo de notas | Aproveitamento precisa ser informado manualmente |

---

## 11. Padrões Sistêmicos Confirmados
> Estes problemas já foram diagnosticados. **Não re-diagnosticar nas próximas sessões** — apenas registrar novas ocorrências com arquivo e linha.

* **Multi-tenancy ausente** — sem `tenant_id` em nenhuma tabela nem query. Impede SaaS. [CONFIRMADO em routes e services]
* **Race condition em tentativas** — padrão check-then-act sem lock ou unique constraint. Mitigado com savepoint em exercícios, mas persiste em provas. [CONFIRMADO]
* **N+1 queries** — queries individuais em loops `for`. Padrão sistêmico esperado em outros módulos.
* **RBAC fraco** — `@login_required` não valida `perfil` na maioria das rotas. Melhorado com `admin_required`/`financeiro_required` mas adoção é limitada. [CONFIRMADO]
* **`_calcular_nota` parcialmente unificada** — `notas_service.py` tem versão canônica, `portal_aluno.py` wrappa, mas 3 outras routes ainda têm cópias. [CONFIRMADO]
* **Deleção física de questões** — remove registros referenciados por respostas históricas. Corrompe histórico retroativamente. [CONFIRMADO em provas e exercícios]
* **HMAC implementado para provas** — timestamp de início e ordem de alternativas são assinados. [CORRIGIDO]
* **Tempo limite enforçado em exercícios** — backend agora valida `tempo_limite`. [CORRIGIDO]
* **Status de frequência inconsistente** — ⚠️ **o registro anterior estava invertido**. Formulário grava `P`/`F`; model declara default `Presente`; `enums.StatusFrequencia` define rótulos por extenso. `calcular_percentual` comparava só `"Presente"` → 0,0% sempre. **CORRIGIDO na v6** via `normalizar_status()` / `is_presente()`, que aceitam `P`, `p`, `Presente`, `presente`. [VERIFICADO contra `cqp.db`]
* **Nota zero oculta no boletim** — `if n.nota` falha para `0.0`. [**CORRIGIDO na v5** — `pdf_service.py:236` usa `is not None`. Ver DT-01]
* **Proxy Cloudinary** — `file_service.py` usa 5 estratégias de URL assinada (`upload`/`private`/`authenticated`/`private_download_url`) com `requests`. [NOVO na v5 — ver §6]
* **Mensalidades duplicadas sem proteção** — `criar_matricula` agora tem guarda de duplicidade. [CORRIGIDO]
* **PDFs expõem dados sensíveis sem controle** — CPF, financeiro, endereço. Sem watermark ou controle de acesso no service. [NÃO CORRIGIDO — ver DT-10]
* **Validação de data com mensagem contraditória** — parse `YYYY-MM-DD` mas mensagem diz `DD/MM/AAAA`. [NÃO CORRIGIDO — ver DT-04]
* **Arredondamento de parcelas de material** — sem ajuste na última parcela. [NÃO CORRIGIDO — ver DT-05]

---

## 12. Novos Serviços e Módulos (pós-v3)

| Módulo | Descrição |
|:---|:---|
| `services/file_service.py` | Abstração de serving de arquivos com headers compatíveis com PDF.js. Suporta arquivos locais e proxy de URLs remotas (Cloudinary). |
| `services/storage_service.py` | Upload e deleção de arquivos no Cloudinary. Suporta prefixo de pasta configurável por cliente. |
| `routes/contrato_admin.py` | Endpoints administrativos para auditoria de aceites de contrato (`GET /admin/alunos/<id>/contrato/aceites`) e reset de assinatura (`POST /admin/alunos/<id>/contrato/reset`). |
| `routes/entradas_caixa.py` ⭐ | Entradas de caixa manuais (tabela `entradas_caixa`). Rotas: `GET/POST /entradas-caixa` (listagem/criação) e `POST /entradas-caixa/<id>/cancelar` (exclusão lógica). Todas com `@financeiro_required`. Helpers: `_validar`, `_listar`, `_usuario`. |
| `models.ContratoAceite` | Tabela imutável de log de aceite de contrato digital com SHA-256, IP e User-Agent. |
| `models.AtividadeLiberada` | Tabela de liberação granular de atividades com `extra_tentativas`. |
| `GET /aluno/csrf-token` | Endpoint heartbeat (`portal_aluno.py:296`) que renova o token/cookie CSRF em páginas longas (provas/exercícios/atividades). Commit `f3923b7`. |
| `exercicios.py` recalculo em lote | Funções `_recalcular_tentativas_sem_nota` (~380-420) e `recalcular_pontos_todos` (~447), além de `_pontos_minimo_aprovacao` (:37) que converte `nota_minima` (0-10) para pontos brutos. |
| `gerar_contrato_assinado` | PDF de comprovante de aceite de contrato digital (versão, hash SHA-256, IP, user-agent) em `pdf_service.py:575-740`. |
| Proxy Cloudinary 5 estratégias | `file_service.py:312-438` tenta URL assinada/private/authenticated/private_download_url em cascata, com `requests`. |
| `services/certificado_pdf.py` ⭐ | Renderer do certificado de conclusão em A4 paisagem sobre moldura gráfica. Função pura: `gerar_certificado(dados, layout) -> bytes`. Irmão de `pdf_service.py` — este cuida de documentos de fluxo (retrato), aquele de layout absoluto (paisagem). Usa `invariant=1` para que a mesma entrada gere sempre os mesmos bytes (base do `hash_sha256`). |
| `services/certificado_layout.py` ⭐ | Carrega e valida `layouts/*.toml`: página, margens, 5 blocos tipográficos, cores, fontes, município, formato de data. Posições fora do código. |
| `services/certificado_service.py` ⭐ | Domínio da emissão: `validar_emissao`, `emitir_certificado` (gera PDF + persiste snapshot), `cancelar_certificado` (lógico), `buscar_por_codigo`, `pdf_do_certificado` (re-render a partir do snapshot). Testável sem Flask. |
| `routes/certificados.py` ⭐ | `GET/POST /aluno/<id>/certificados` (histórico + emissão), `GET /certificados/<id>/pdf`, `POST /certificados/<id>/cancelar`. Upload ao Cloudinary é opcional: sem credenciais o PDF é re-renderizado do snapshot. |
| `models.Certificado` ⭐ | Snapshot imutável do certificado emitido + `codigo_verificacao` (único), `hash_sha256`, `layout_id`, autor e timestamps. Cancelamento é lógico (`status=CANCELADO`), nunca exclusão. |
| `layouts/certificado_cqp.toml` ⭐ | Especificação visual do certificado (v1). Editar aqui não exige tocar em Python. |
| `static/fonts/` ⭐ | Liberation Sans (4 pesos) + `LICENSE-Liberation.txt` (SIL OFL 1.1). Métricas idênticas ao Arial, sem depender de fonte do SO. |
| `tests/` ⭐ | **Primeira suíte de testes do projeto** (144 testes). `conftest.py` usa SQLite em memória — nunca toca `cqp.db`. |

---

## 13. Checklist de Modernização (SaaS)

| Item | Bloqueador | Esforço |
|:---|:---|:---|
| Migrar SQLite → PostgreSQL | Sim — sem writes concorrentes | Alto |
| Adicionar `tenant_id` em todas as tabelas | Sim — sem multi-tenancy | Alto |
| Unificar `_calcular_nota` nas 3 rotas restantes | Não | Baixo |
| ~~Corrigir `gerar_historico_frequencia`~~ ✅ **Feito na v6** — o bug real estava em `calcular_percentual`, não no PDF | Não | Baixo |
| ~~Corrigir `gerar_boletim_notas` (nota zero → `if n is not None`)~~ ✅ **Feito na v5** (`pdf_service.py:236`) | Não | Baixo |
| Adicionar `extra_tentativas` no painel de liberações + `AcessoConteudoCurso` | Não | Médio |
| Validar input numérico em `cursos.py`/`despesas.py` (DT-22) | Não | Baixo |
| Corrigir mensagem de erro de data em `_validar_data` | Não | Baixo |
| Migrar storage de imagens do PDF service para Cloudinary | Não | Médio |
| Adicionar `unique_constraint` ou lock em tentativas de prova | Não | Médio |
| Centralizar lógica de exercícios em um service | Não | Médio |
| Substituir `Limiter(memory)` por Redis em produção | Não | Médio |
| Implementar RBAC completo em todas as rotas | Não | Alto |