"""Execute uma vez para criar os indices de performance no banco.

Uso:
    python scripts/criar_indices.py
"""
import sqlite3
import os
import sys

db_path = "/home/site/wwwroot/cqp.db"
if not os.path.exists(db_path):
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cqp.db")

if not os.path.exists(db_path):
    print(f"ERRO: banco nao encontrado em {db_path}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

indices = [
    "CREATE INDEX IF NOT EXISTS idx_mensalidades_aluno    ON mensalidades(aluno_id)",
    "CREATE INDEX IF NOT EXISTS idx_mensalidades_status   ON mensalidades(status)",
    "CREATE INDEX IF NOT EXISTS idx_mensalidades_vencimento ON mensalidades(vencimento)",
    "CREATE INDEX IF NOT EXISTS idx_mensalidades_pagamento ON mensalidades(data_pagamento)",
    "CREATE INDEX IF NOT EXISTS idx_matriculas_aluno      ON matriculas(aluno_id)",
    "CREATE INDEX IF NOT EXISTS idx_matriculas_curso      ON matriculas(curso_id)",
    "CREATE INDEX IF NOT EXISTS idx_matriculas_data       ON matriculas(data_matricula)",
    "CREATE INDEX IF NOT EXISTS idx_frequencias_aluno     ON frequencias(aluno_id, curso_id)",
    "CREATE INDEX IF NOT EXISTS idx_frequencias_data      ON frequencias(data)",
    "CREATE INDEX IF NOT EXISTS idx_notas_aluno           ON notas(aluno_id, curso_id)",
    "CREATE INDEX IF NOT EXISTS idx_alunos_status         ON alunos(status)",
    "CREATE INDEX IF NOT EXISTS idx_despesas_data         ON despesas(data)",
    "CREATE INDEX IF NOT EXISTS idx_despesas_recorrente   ON despesas(recorrente)",
]

for sql in indices:
    c.execute(sql)
    nome = sql.split("idx_")[1].split(" ")[0]
    print(f"  ✅ idx_{nome}")

conn.commit()
conn.close()
print("\nTodos os indices criados com sucesso.")
