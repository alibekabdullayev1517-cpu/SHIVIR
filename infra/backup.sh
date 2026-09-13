#!/usr/bin/env bash
# Daily Postgres backup for Shivir, run via the shivir-backup.timer systemd
# timer (see infra/systemd/shivir-backup.timer.example) rather than cron.
#
# Credentials come from the app's own .env (POSTGRES_PASSWORD) — no separate
# credential to create, export, or keep in sync. Only that one variable is
# read out of .env (never the whole file, which also holds BOT_TOKEN/
# SECRET_KEY) and it's passed to pg_dump via the PGPASSWORD environment
# variable rather than embedded in a connection URL — a URL on the pg_dump
# command line would be visible to any local user via `ps aux`; PGPASSWORD
# is not.

set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/shivir/.env}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/shivir}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
PG_HOST="${PG_HOST:-localhost}"
PG_PORT="${PG_PORT:-5432}"
PG_USER="${PG_USER:-shivir}"
PG_DATABASE="${PG_DATABASE:-shivir}"

if [ ! -f "$ENV_FILE" ]; then
    echo "ENV_FILE not found: $ENV_FILE" >&2
    exit 1
fi

# `|| true` on the grep: under `set -e`+`pipefail`, grep finding no match
# (exit 1) would otherwise abort the script right here, silently, before the
# explicit -z check below ever runs — losing the clear error message.
POSTGRES_PASSWORD="$(grep -E '^POSTGRES_PASSWORD=' "$ENV_FILE" | tail -n1 | cut -d '=' -f2- || true)"
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "POSTGRES_PASSWORD not set in $ENV_FILE" >&2
    exit 1
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
    --host="$PG_HOST" --port="$PG_PORT" --username="$PG_USER" --dbname="$PG_DATABASE" \
    --format=custom --file="$BACKUP_DIR/shivir-$TIMESTAMP.dump"

find "$BACKUP_DIR" -name 'shivir-*.dump' -mtime "+$RETENTION_DAYS" -delete

echo "Backup written to $BACKUP_DIR/shivir-$TIMESTAMP.dump"
