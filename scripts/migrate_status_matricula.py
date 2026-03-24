"""
Migração: padroniza matriculas.status para MAIÚSCULO.
Executar uma vez: python scripts/migrate_status_matricula.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app
from db import db

app = create_app()
with app.app_context():
    result = db.session.execute(
        db.text("UPDATE matriculas SET status = UPPER(status) WHERE status != UPPER(status)")
    )
    db.session.commit()
    print(f"Registros atualizados: {result.rowcount}")
    print("Valores distintos após migração:")
    rows = db.session.execute(db.text("SELECT DISTINCT status FROM matriculas")).fetchall()
    for r in rows:
        print(f"  {r[0]}")
