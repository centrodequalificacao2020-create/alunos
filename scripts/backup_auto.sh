#!/bin/bash
# =============================================================
# backup_auto.sh — Backup automático do banco SQLite
# Agendar via cron no PythonAnywhere:
#   0 3 * * * /bin/bash /home/<usuario>/alunos/scripts/backup_auto.sh
# =============================================================

DB_PATH="/home/site/wwwroot/cqp.db"
BACKUP_DIR="/home/site/wwwroot/backups"
DATE=$(date +%Y-%m-%d_%H-%M)
MAX_BACKUPS=30   # mantém últimos 30 backups

mkdir -p "$BACKUP_DIR"

# Copia binária do banco (segura mesmo com WAL)
sqlite3 "$DB_PATH" ".backup '${BACKUP_DIR}/cqp_${DATE}.db'"

# Remove backups antigos além do limite
ls -t "$BACKUP_DIR"/*.db 2>/dev/null | tail -n +$((MAX_BACKUPS+1)) | xargs rm -f

echo "[$(date)] Backup gerado: cqp_${DATE}.db" >> "$BACKUP_DIR/backup.log"
