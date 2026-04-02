-- ============================================================
-- DIAGNÓSTICO COMPLETO - BANCO MENSALIDADES
-- Sistema Escolar | Gerado em 02/04/2026
-- Rodar no SQLite: sqlite3 cqp.db < diagnostico_mensalidades.sql
-- ============================================================

.headers on
.mode column

-- ============================================================
-- BLOCO 1: SAÚDE GERAL DA TABELA
-- ============================================================

-- 1.1 Total de registros e distribuição por status
SELECT 
    status,
    COUNT(*) as qtd,
    ROUND(SUM(valor), 2) as valor_total,
    ROUND(AVG(valor), 2) as ticket_medio
FROM mensalidades
GROUP BY status
ORDER BY qtd DESC;

-- 1.2 Problema de CASE no campo tipo (bug confirmado)
SELECT 
    tipo,
    COUNT(*) as qtd,
    ROUND(SUM(valor), 2) as valor_total
FROM mensalidades
GROUP BY tipo
ORDER BY tipo;

-- 1.3 Quantos registros seriam afetados pela normalização de case
SELECT 
    LOWER(tipo) as tipo_normalizado,
    COUNT(*) as qtd_atual,
    SUM(CASE WHEN tipo != LOWER(tipo) THEN 1 ELSE 0 END) as qtd_com_case_errado
FROM mensalidades
GROUP BY LOWER(tipo)
ORDER BY tipo_normalizado;


-- ============================================================
-- BLOCO 2: SUSPEITA DE DUPLICATAS
-- ============================================================

-- 2.1 Duplicatas EXATAS: mesmo aluno, mesmo valor, mesmo vencimento, mesmo tipo (normalizado)
SELECT 
    aluno_id,
    LOWER(tipo) as tipo,
    valor,
    vencimento,
    COUNT(*) as ocorrencias,
    GROUP_CONCAT(id, ', ') as ids_afetados
FROM mensalidades
GROUP BY aluno_id, LOWER(tipo), valor, vencimento
HAVING COUNT(*) > 1
ORDER BY ocorrencias DESC, aluno_id;

-- 2.2 Contagem de alunos afetados por duplicatas exatas
SELECT COUNT(DISTINCT aluno_id) as alunos_com_duplicata
FROM (
    SELECT aluno_id
    FROM mensalidades
    GROUP BY aluno_id, LOWER(tipo), valor, vencimento
    HAVING COUNT(*) > 1
);

-- 2.3 Valor total "duplicado" (quanto está sendo cobrado a mais por duplicatas)
SELECT 
    ROUND(SUM(valor * (ocorrencias - 1)), 2) as valor_cobrado_em_duplicata
FROM (
    SELECT valor, COUNT(*) as ocorrencias
    FROM mensalidades
    GROUP BY aluno_id, LOWER(tipo), valor, vencimento
    HAVING COUNT(*) > 1
);

-- 2.4 Alunos com MAIS de uma mensalidade pendente no mesmo mês (pode ser 2 cursos OU duplicata)
SELECT 
    aluno_id,
    strftime('%Y-%m', vencimento) as mes,
    COUNT(*) as qtd_mensalidades,
    ROUND(SUM(valor), 2) as total_mes,
    GROUP_CONCAT(id || '(R$' || valor || ')', ' | ') as detalhes
FROM mensalidades
WHERE LOWER(tipo) = 'mensalidade'
  AND status = 'Pendente'
GROUP BY aluno_id, strftime('%Y-%m', vencimento)
HAVING COUNT(*) > 1
ORDER BY qtd_mensalidades DESC, aluno_id, mes;


-- ============================================================
-- BLOCO 3: DIAGNÓSTICO DO ALUNO 38 (exemplo - troque o id)
-- ============================================================

-- 3.1 Quem é o aluno 38
SELECT id, nome, cpf, email, telefone, status
FROM alunos
WHERE id = 38;

-- 3.2 Matrículas do aluno 38 (confirma se tem 1 ou 2 cursos)
SELECT 
    m.id as matricula_id,
    m.aluno_id,
    c.nome as curso,
    m.data_matricula,
    m.status as status_matricula
FROM matriculas m
LEFT JOIN cursos c ON c.id = m.curso_id
WHERE m.aluno_id = 38
ORDER BY m.data_matricula;

-- 3.3 Histórico completo de mensalidades do aluno 38
SELECT 
    id,
    tipo,
    valor,
    vencimento,
    status,
    data_pagamento,
    CASE 
        WHEN status = 'Pendente' AND date(vencimento) < date('now') THEN '*** VENCIDO ***'
        WHEN status = 'Pendente' AND date(vencimento) = date('now') THEN '*** VENCE HOJE ***'
        ELSE ''
    END as alerta
FROM mensalidades
WHERE aluno_id = 38
ORDER BY vencimento, id;

-- 3.4 Resumo financeiro do aluno 38
SELECT 
    status,
    LOWER(tipo) as tipo,
    COUNT(*) as qtd,
    ROUND(SUM(valor), 2) as total
FROM mensalidades
WHERE aluno_id = 38
GROUP BY status, LOWER(tipo)
ORDER BY status, tipo;


-- ============================================================
-- BLOCO 4: INADIMPLÊNCIA ATUAL (vencidas e não pagas)
-- ============================================================

-- 4.1 Total vencido por mês
SELECT 
    strftime('%Y-%m', vencimento) as mes_vencimento,
    COUNT(*) as qtd_registros,
    COUNT(DISTINCT aluno_id) as qtd_alunos,
    ROUND(SUM(valor), 2) as valor_vencido
FROM mensalidades
WHERE status = 'Pendente'
  AND date(vencimento) < date('now')
GROUP BY strftime('%Y-%m', vencimento)
ORDER BY mes_vencimento;

-- 4.2 Alunos inadimplentes com valor total em aberto
SELECT 
    m.aluno_id,
    a.nome,
    COUNT(*) as parcelas_vencidas,
    ROUND(SUM(m.valor), 2) as total_em_atraso,
    MIN(m.vencimento) as primeira_parcela_vencida
FROM mensalidades m
LEFT JOIN alunos a ON a.id = m.aluno_id
WHERE m.status = 'Pendente'
  AND date(m.vencimento) < date('now')
GROUP BY m.aluno_id, a.nome
ORDER BY total_em_atraso DESC;

-- 4.3 Top 10 maiores devedores
SELECT 
    m.aluno_id,
    a.nome,
    ROUND(SUM(m.valor), 2) as total_em_atraso,
    MIN(m.vencimento) as desde_quando
FROM mensalidades m
LEFT JOIN alunos a ON a.id = m.aluno_id
WHERE m.status = 'Pendente'
  AND date(m.vencimento) < date('now')
GROUP BY m.aluno_id, a.nome
ORDER BY total_em_atraso DESC
LIMIT 10;


-- ============================================================
-- BLOCO 5: RECEITA - VISÃO MENSAL
-- ============================================================

-- 5.1 Recebimentos por mês (pagos)
SELECT 
    strftime('%Y-%m', data_pagamento) as mes_pagamento,
    COUNT(*) as qtd_pagamentos,
    COUNT(DISTINCT aluno_id) as qtd_alunos,
    ROUND(SUM(valor), 2) as valor_recebido
FROM mensalidades
WHERE status = 'Pago'
  AND data_pagamento IS NOT NULL
GROUP BY strftime('%Y-%m', data_pagamento)
ORDER BY mes_pagamento DESC
LIMIT 12;

-- 5.2 Projeção de receita futura (pendentes com vencimento futuro)
SELECT 
    strftime('%Y-%m', vencimento) as mes_vencimento,
    COUNT(*) as qtd_lancamentos,
    COUNT(DISTINCT aluno_id) as qtd_alunos,
    ROUND(SUM(valor), 2) as receita_esperada
FROM mensalidades
WHERE status = 'Pendente'
  AND date(vencimento) >= date('now')
GROUP BY strftime('%Y-%m', vencimento)
ORDER BY mes_vencimento
LIMIT 12;

-- 5.3 Comparativo: esperado x recebido em abril/2026
SELECT 
    'Esperado (Pendente)' as situacao,
    COUNT(*) as qtd,
    ROUND(SUM(valor), 2) as valor
FROM mensalidades
WHERE strftime('%Y-%m', vencimento) = '2026-04'
  AND status = 'Pendente'
UNION ALL
SELECT 
    'Recebido (Pago)' as situacao,
    COUNT(*) as qtd,
    ROUND(SUM(valor), 2) as valor
FROM mensalidades
WHERE strftime('%Y-%m', data_pagamento) = '2026-04'
  AND status = 'Pago';


-- ============================================================
-- BLOCO 6: VERIFICAÇÃO DE INTEGRIDADE REFERENCIAL
-- ============================================================

-- 6.1 Mensalidades com aluno_id inexistente na tabela alunos
SELECT 
    m.aluno_id,
    COUNT(*) as qtd_registros_orfaos,
    ROUND(SUM(m.valor), 2) as valor_total_orfao
FROM mensalidades m
LEFT JOIN alunos a ON a.id = m.aluno_id
WHERE a.id IS NULL
GROUP BY m.aluno_id
ORDER BY qtd_registros_orfaos DESC;

-- 6.2 Mensalidades com status Pago mas sem data_pagamento (bug)
SELECT id, aluno_id, tipo, valor, vencimento, status, data_pagamento
FROM mensalidades
WHERE status = 'Pago'
  AND (data_pagamento IS NULL OR data_pagamento = '');

-- 6.3 Mensalidades com data_pagamento preenchida mas status Pendente (bug)
SELECT id, aluno_id, tipo, valor, vencimento, status, data_pagamento
FROM mensalidades
WHERE status = 'Pendente'
  AND data_pagamento IS NOT NULL
  AND data_pagamento != '';

-- 6.4 Valores negativos ou zerados (anômalos)
SELECT id, aluno_id, tipo, valor, vencimento, status
FROM mensalidades
WHERE valor <= 0;


-- ============================================================
-- BLOCO 7: SCRIPT DE CORREÇÃO (DESCOMENTE APÓS CONFIRMAR!)
-- ============================================================

-- PASSO 1: Ver exatamente o que vai mudar antes do UPDATE
SELECT id, aluno_id, tipo, LOWER(tipo) as tipo_novo
FROM mensalidades
WHERE tipo != LOWER(tipo)
LIMIT 20;

-- PASSO 2 (DESCOMENTE PARA EXECUTAR): Normalizar o campo tipo
-- UPDATE mensalidades SET tipo = LOWER(tipo) WHERE tipo != LOWER(tipo);

-- PASSO 3: Ver duplicatas exatas que seriam removidas
SELECT 
    aluno_id, LOWER(tipo) as tipo, valor, vencimento,
    GROUP_CONCAT(id, ', ') as todos_os_ids,
    MIN(id) as id_manter
FROM mensalidades
WHERE status = 'Pendente'
GROUP BY aluno_id, LOWER(tipo), valor, vencimento
HAVING COUNT(*) > 1
ORDER BY aluno_id;

-- PASSO 4 (DESCOMENTE PARA EXECUTAR): Remover duplicatas mantendo o menor id
-- Segurança: só remove Pendentes, NUNCA toca em registros Pagos
-- DELETE FROM mensalidades
-- WHERE id NOT IN (
--     SELECT MIN(id)
--     FROM mensalidades
--     GROUP BY aluno_id, LOWER(tipo), valor, vencimento
-- )
-- AND status = 'Pendente';
