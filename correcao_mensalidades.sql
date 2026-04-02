-- ============================================================
-- SCRIPT DE CORREÇÃO - BANCO MENSALIDADES (cqp.db)
-- Gerado em 02/04/2026
-- EXECUTE PASSO A PASSO - leia os SELECTs antes de cada UPDATE/DELETE
-- ============================================================

.headers on
.mode column

-- ============================================================
-- PASSO 0: BACKUP OBRIGATÓRIO ANTES DE TUDO
-- No terminal, ANTES de abrir o sqlite3:
--   cp cqp.db cqp_backup_02042026.db
-- ============================================================

-- ============================================================
-- PASSO 1: VERIFICAR MATRÍCULAS DUPLICADAS
-- ============================================================

-- 1.1 Ver matrículas duplicadas (mesmo aluno, mesmo curso)
SELECT 
    m.aluno_id,
    a.nome,
    m.curso_id,
    c.nome as curso,
    COUNT(*) as qtd_matriculas,
    GROUP_CONCAT(m.id, ', ') as ids_matriculas,
    GROUP_CONCAT(m.data_matricula, ', ') as datas
FROM matriculas m
LEFT JOIN alunos a ON a.id = m.aluno_id
LEFT JOIN cursos c ON c.id = m.curso_id
GROUP BY m.aluno_id, m.curso_id
HAVING COUNT(*) > 1
ORDER BY m.aluno_id;

-- 1.2 Detalhe completo das matrículas da MARCELLA (aluno 38)
SELECT m.id, m.aluno_id, c.nome as curso, m.data_matricula, m.status
FROM matriculas m
LEFT JOIN cursos c ON c.id = m.curso_id
WHERE m.aluno_id = 38
ORDER BY m.curso_id, m.data_matricula;

-- 1.3 Detalhe das matrículas do aluno 94 (MAÍSA)
SELECT m.id, m.aluno_id, c.nome as curso, m.data_matricula, m.status
FROM matriculas m
LEFT JOIN cursos c ON c.id = m.curso_id
WHERE m.aluno_id = 94
ORDER BY m.curso_id, m.data_matricula;

-- ============================================================
-- CONFIRME OS RESULTADOS ACIMA ANTES DE CONTINUAR
-- ============================================================

-- ============================================================
-- PASSO 2: CORRIGIR CASE DO CAMPO TIPO (seguro, sem perda)
-- ============================================================

-- 2.1 Ver quantos registros serão afetados
SELECT COUNT(*) as registros_a_corrigir
FROM mensalidades
WHERE tipo != LOWER(tipo);

-- 2.2 EXECUTAR correção de case
UPDATE mensalidades 
SET tipo = LOWER(tipo) 
WHERE tipo != LOWER(tipo);

-- 2.3 Confirmar que não há mais case errado
SELECT tipo, COUNT(*) as qtd
FROM mensalidades
GROUP BY tipo
ORDER BY tipo;

-- ============================================================
-- PASSO 3: IDENTIFICAR E REMOVER DUPLICATAS DE MENSALIDADES
-- ============================================================

-- 3.1 Confirmar duplicatas antes de deletar
SELECT 
    aluno_id,
    tipo,
    valor,
    vencimento,
    GROUP_CONCAT(id, ', ') as todos_ids,
    MIN(id) as id_manter,
    COUNT(*) as ocorrencias
FROM mensalidades
WHERE status = 'Pendente'
GROUP BY aluno_id, tipo, valor, vencimento
HAVING COUNT(*) > 1
ORDER BY aluno_id;

-- 3.2 Ver exatamente quais IDs serão deletados
SELECT id, aluno_id, tipo, valor, vencimento, status
FROM mensalidades
WHERE status = 'Pendente'
  AND id NOT IN (
      SELECT MIN(id)
      FROM mensalidades
      WHERE status = 'Pendente'
      GROUP BY aluno_id, tipo, valor, vencimento
  )
  AND (aluno_id, tipo, valor, vencimento) IN (
      SELECT aluno_id, tipo, valor, vencimento
      FROM mensalidades
      WHERE status = 'Pendente'
      GROUP BY aluno_id, tipo, valor, vencimento
      HAVING COUNT(*) > 1
  )
ORDER BY aluno_id, vencimento;

-- 3.3 EXECUTAR deleção de duplicatas
-- Mantém o menor id de cada grupo, remove os demais
-- NUNCA toca em registros com status != 'Pendente'
DELETE FROM mensalidades
WHERE status = 'Pendente'
  AND id NOT IN (
      SELECT MIN(id)
      FROM mensalidades
      WHERE status = 'Pendente'
      GROUP BY aluno_id, tipo, valor, vencimento
  )
  AND (aluno_id, tipo, valor, vencimento) IN (
      SELECT aluno_id, tipo, valor, vencimento
      FROM mensalidades
      WHERE status = 'Pendente'
      GROUP BY aluno_id, tipo, valor, vencimento
      HAVING COUNT(*) > 1
  );

-- 3.4 Confirmar que não há mais duplicatas
SELECT COUNT(*) as duplicatas_restantes
FROM mensalidades
WHERE status = 'Pendente'
GROUP BY aluno_id, tipo, valor, vencimento
HAVING COUNT(*) > 1;

-- ============================================================
-- PASSO 4: CORRIGIR DATA DE PAGAMENTO CORROMPIDA (ano 0026)
-- ============================================================

-- 4.1 Identificar o registro com data corrompida
SELECT id, aluno_id, tipo, valor, vencimento, status, data_pagamento
FROM mensalidades
WHERE data_pagamento LIKE '0026-%';

-- 4.2 EXECUTAR correção (substitui 0026 por 2026)
UPDATE mensalidades
SET data_pagamento = '2026' || SUBSTR(data_pagamento, 5)
WHERE data_pagamento LIKE '0026-%';

-- 4.3 Confirmar correção (deve retornar 0 linhas)
SELECT id, aluno_id, data_pagamento
FROM mensalidades
WHERE data_pagamento LIKE '0026-%';

-- ============================================================
-- PASSO 5: VERIFICAR OUTROS BUGS DE INTEGRIDADE
-- ============================================================

-- 5.1 Pagos sem data_pagamento
SELECT id, aluno_id, tipo, valor, vencimento, status, data_pagamento
FROM mensalidades
WHERE status = 'Pago'
  AND (data_pagamento IS NULL OR data_pagamento = '');

-- 5.2 Pendentes com data_pagamento preenchida
SELECT id, aluno_id, tipo, valor, vencimento, status, data_pagamento
FROM mensalidades
WHERE status = 'Pendente'
  AND data_pagamento IS NOT NULL
  AND data_pagamento != '';

-- 5.3 Datas de pagamento fora do range esperado
SELECT id, aluno_id, data_pagamento
FROM mensalidades
WHERE data_pagamento IS NOT NULL
  AND data_pagamento != ''
  AND (
      data_pagamento < '2020-01-01'
      OR data_pagamento > '2030-12-31'
  )
ORDER BY data_pagamento;

-- ============================================================
-- PASSO 6: TRATAR INADIMPLÊNCIA ANTIGA (aluno 116 - desde 2016)
-- ============================================================

-- 6.1 Ver todos os registros da PATRÍCIA (aluno 116)
SELECT id, tipo, valor, vencimento, status, data_pagamento
FROM mensalidades
WHERE aluno_id = 116
ORDER BY vencimento;

-- 6.2 Ver situação atual da matrícula dela
SELECT m.id, m.aluno_id, c.nome as curso, m.data_matricula, m.status
FROM matriculas m
LEFT JOIN cursos c ON c.id = m.curso_id
WHERE m.aluno_id = 116;

-- ATENÇÃO: Decida com o cliente antes de executar:
-- Opção A - Marcar como cancelado (preserva histórico, some da inadimplência):
-- UPDATE mensalidades 
-- SET status = 'Cancelado'
-- WHERE aluno_id = 116 
--   AND date(vencimento) < '2020-01-01';

-- Opção B - Deletar se for lixo de migração:
-- DELETE FROM mensalidades
-- WHERE aluno_id = 116
--   AND date(vencimento) < '2020-01-01';

-- ============================================================
-- PASSO 7: RELATÓRIO FINAL PÓS-CORREÇÃO
-- ============================================================

-- 7.1 Resumo geral após correções
SELECT 
    status,
    COUNT(*) as qtd,
    ROUND(SUM(valor), 2) as valor_total
FROM mensalidades
GROUP BY status
ORDER BY qtd DESC;

-- 7.2 Confirmar que o case foi normalizado
SELECT tipo, COUNT(*) as qtd
FROM mensalidades
GROUP BY tipo
ORDER BY tipo;

-- 7.3 Receita pendente por mês (atualizada)
SELECT 
    strftime('%Y-%m', vencimento) as mes,
    COUNT(*) as lancamentos,
    COUNT(DISTINCT aluno_id) as alunos,
    ROUND(SUM(valor), 2) as receita_esperada
FROM mensalidades
WHERE status = 'Pendente'
  AND date(vencimento) >= date('now')
GROUP BY strftime('%Y-%m', vencimento)
ORDER BY mes
LIMIT 12;

-- 7.4 Inadimplência real (vencidas a partir de 2024)
SELECT 
    m.aluno_id,
    a.nome,
    COUNT(*) as parcelas_vencidas,
    ROUND(SUM(m.valor), 2) as total_em_atraso,
    MIN(m.vencimento) as desde_quando
FROM mensalidades m
LEFT JOIN alunos a ON a.id = m.aluno_id
WHERE m.status = 'Pendente'
  AND date(m.vencimento) < date('now')
  AND date(m.vencimento) >= '2024-01-01'
GROUP BY m.aluno_id, a.nome
ORDER BY total_em_atraso DESC;

-- FIM DO SCRIPT
-- ============================================================
