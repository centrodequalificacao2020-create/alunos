-- Migration: contrato_assinado_nullable
-- Data: 2026-05-27
-- Descricao: Torna contrato_assinado nullable para distinguir tres estados:
--   NULL  = aluno cadastrado antes da implantacao do contrato digital (isento)
--   0     = secretaria solicitou nova assinatura (sera redirecionado no login)
--   1     = contrato assinado
--
-- INSTRUCOES DE EXECUCAO:
--   1. Faca backup do banco antes de executar.
--   2. Execute este script uma unica vez no banco de producao:
--        sqlite3 database.db < migrations/contrato_assinado_nullable.sql
--        (ou cole no cliente SQL de sua preferencia)
--   3. Reinicie a aplicacao apos a execucao.
--
-- IMPORTANTE: O SQLite nao suporta ALTER COLUMN diretamente.
-- A estrategia abaixo recria a tabela preservando todos os dados.

PRAGMA foreign_keys = OFF;
BEGIN TRANSACTION;

-- 1. Cria tabela temporaria com a nova definicao do campo
CREATE TABLE alunos_new (
    id                     INTEGER PRIMARY KEY,
    nome                   VARCHAR(120) NOT NULL,
    cpf                    VARCHAR(14),
    rg                     VARCHAR(20),
    data_nascimento        VARCHAR(10),
    telefone               VARCHAR(20),
    whatsapp               VARCHAR(20),
    telefone_contato       VARCHAR(20),
    email                  VARCHAR(120),
    endereco               VARCHAR(200),
    complemento            VARCHAR(100),
    bairro                 VARCHAR(100),
    cidade                 VARCHAR(100),
    estado                 VARCHAR(2),
    cep                    VARCHAR(9),
    status                 VARCHAR(40),
    curso_id               INTEGER REFERENCES cursos(id),
    responsavel_nome       VARCHAR(120),
    responsavel_cpf        VARCHAR(14),
    responsavel_telefone   VARCHAR(20),
    responsavel_parentesco VARCHAR(40),
    senha                  VARCHAR(256),
    -- Campo alterado: nullable=True, sem server_default
    -- NULL = isento (aluno antigo), 0 = pendente assinatura, 1 = assinado
    contrato_assinado      BOOLEAN,
    contrato_assinado_em   VARCHAR(19)
);

-- 2. Copia os dados: quem ja assinou (1) mantem True;
--    quem nao assinou (0) recebe NULL (isento por ser aluno antigo)
INSERT INTO alunos_new
SELECT
    id, nome, cpf, rg, data_nascimento,
    telefone, whatsapp, telefone_contato, email, endereco,
    complemento, bairro, cidade, estado, cep,
    status, curso_id,
    responsavel_nome, responsavel_cpf, responsavel_telefone, responsavel_parentesco,
    senha,
    CASE
        WHEN contrato_assinado = 1 THEN 1
        ELSE NULL   -- 0 vira NULL: aluno antigo, isento
    END AS contrato_assinado,
    contrato_assinado_em
FROM alunos;

-- 3. Substitui a tabela antiga
DROP TABLE alunos;
ALTER TABLE alunos_new RENAME TO alunos;

COMMIT;
PRAGMA foreign_keys = ON;
