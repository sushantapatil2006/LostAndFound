#!/usr/bin/env bash
# ==============================================================================
# Automated MySQL Database Backup Script for Campus Lost & Found Portal
# ==============================================================================
# Usage:
#   ./scripts/backup-db.sh [/path/to/backup/dir]
#
# Cron Example (daily at 02:00 AM):
#   0 2 * * * /opt/lostandfound/scripts/backup-db.sh /opt/backups >> /var/log/db_backup.log 2>&1
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$APP_DIR"

BACKUP_DIR="${1:-/opt/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP="$(date +'%Y-%m-%d_%H%M%S')"
BACKUP_FILENAME="lostandfound_db_${TIMESTAMP}.sql.gz"
BACKUP_FILEPATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [ ! -f .env ]; then
    echo "[$(date)] ERROR: Missing .env file in ${APP_DIR}."
    exit 1
fi

set -a
# shellcheck disable=SC1090
source .env
set +a

DB_NAME="${MYSQL_DATABASE:-lost_found_portal}"
DB_USER="${MYSQL_USER:-lostfound}"
COMPOSE_FILE="docker-compose.prod.yml"

echo "[$(date)] Starting backup of database '${DB_NAME}'..."

# Verify MySQL container is healthy
if ! docker compose -f "$COMPOSE_FILE" ps mysql | grep -q "(healthy)"; then
    echo "[$(date)] WARNING: MySQL service does not report healthy status. Attempting dump..."
fi

# Execute mysqldump via docker compose exec without exposing password in process arguments
# Using MYSQL_PWD environment variable inside container avoids logging password
if docker compose -f "$COMPOSE_FILE" exec -T \
    -e MYSQL_PWD="$MYSQL_PASSWORD" \
    mysql mysqldump \
      --single-transaction \
      --quick \
      --routines \
      --triggers \
      -u "$DB_USER" \
      "$DB_NAME" | gzip -9 > "$BACKUP_FILEPATH"; then

    # Verify backup file size
    FILE_SIZE="$(stat -c%s "$BACKUP_FILEPATH" 2>/dev/null || stat -f%z "$BACKUP_FILEPATH" 2>/dev/null || echo 0)"
    if [ "$FILE_SIZE" -le 100 ]; then
        echo "[$(date)] ERROR: Backup file is empty or suspiciously small (${FILE_SIZE} bytes). Removing."
        rm -f "$BACKUP_FILEPATH"
        exit 1
    fi

    chmod 600 "$BACKUP_FILEPATH"
    echo "[$(date)] SUCCESS: Backup created at ${BACKUP_FILEPATH} (${FILE_SIZE} bytes)."
else
    echo "[$(date)] ERROR: mysqldump execution failed."
    rm -f "$BACKUP_FILEPATH"
    exit 1
fi

# Rotate backups older than retention days
echo "[$(date)] Pruning backups older than ${RETENTION_DAYS} days in ${BACKUP_DIR}..."
find "$BACKUP_DIR" -name "lostandfound_db_*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" -delete

echo "[$(date)] Backup process completed successfully."

# ==============================================================================
# HOW TO RESTORE FROM THIS BACKUP:
#
# 1. Uncompress and stream dump into the running MySQL container:
#    gunzip < /opt/backups/lostandfound_db_YYYY-MM-DD_HHMMSS.sql.gz | \
#      docker compose -f docker-compose.prod.yml exec -T \
#        -e MYSQL_PWD="your-mysql-password" \
#        mysql mysql -u lostfound lost_found_portal
# ==============================================================================
