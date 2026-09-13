#!/usr/bin/env bash
# Nightly Postgres backup for Shivir. Intended to run via cron, e.g.:
#   0 3 * * * /opt/shivir/infra/backup.sh >> /var/log/shivir-backup.log 2>&1
#
# Requires PG_DUMP_URL — a plain `postgresql://user:pass@host:port/db` URL.
# (Deliberately separate from the app's DATABASE_URL, which uses the
# `postgresql+asyncpg://` SQLAlchemy driver scheme that pg_dump doesn't
# understand.) BACKUP_DIR must be writable. Keeps the last 14 daily backups;
# adjust retention as needed.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/shivir}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

pg_dump --dbname="$PG_DUMP_URL" --format=custom --file="$BACKUP_DIR/shivir-$TIMESTAMP.dump"

find "$BACKUP_DIR" -name 'shivir-*.dump' -mtime "+$RETENTION_DAYS" -delete

echo "Backup written to $BACKUP_DIR/shivir-$TIMESTAMP.dump"
