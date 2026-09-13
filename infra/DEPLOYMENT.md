# SHIVIR V1 — Deployment Guide

Target: a single small Linux VPS. No Kubernetes, no microservices — per the
master plan, that's a scale-triggered decision for later, not a V1 default.

## 1. Prerequisites

- A Linux VPS (2 vCPU / 4GB RAM is comfortably enough for V1 traffic)
- Python 3.13, PostgreSQL 16, Redis 7, Nginx
- A domain name pointed at the VPS (for the sender web page's public URL and
  HTTPS)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## 2. Get the code onto the server

```bash
git clone <your-repo-url> /opt/shivir
cd /opt/shivir
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in real values — **never commit this file**:

- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `BOT_TOKEN` — from @BotFather
- `BOT_USERNAME` — your bot's username (no `@`)
- `WEB_BASE_URL` — the public HTTPS URL senders will land on, e.g. `https://shivir.example.com`
- `POSTGRES_PASSWORD` — a strong random value (`python -c "import secrets; print(secrets.token_urlsafe(24))"`); used by `infra/docker-compose.yml` to set the Postgres superuser password — compose refuses to start without it
- `DATABASE_URL` — `postgresql+asyncpg://shivir:<same password as POSTGRES_PASSWORD>@localhost:5432/shivir`
- `REDIS_URL` — `redis://localhost:6379/0`
- `ADMIN_TG_USER_IDS` — your own Telegram user ID(s), comma-separated, for `/modqueue` access

## 4. Database and Redis

Either install Postgres/Redis directly on the VPS, or run them via the
provided Compose file (works equally well in production, one less thing to
manage by hand). Run it from the repo root with `--env-file .env` — the
compose file lives in `infra/`, but `.env` (with `POSTGRES_PASSWORD`) is at
the repo root, and compose only auto-discovers a `.env` next to the compose
file itself:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up -d
```

Both Postgres (5432) and Redis (6379) are bound to `127.0.0.1` only — reachable
from the app running on this same host (as `localhost`, matching `DATABASE_URL`/
`REDIS_URL` in `.env` unchanged), never from outside the machine.

Then run migrations:

```bash
.venv/bin/alembic upgrade head
```

To roll back one revision if a migration goes wrong: `.venv/bin/alembic downgrade -1`.

## 5. Running the three processes

V1 is three long-running processes: the bot (long polling), the web app
(uvicorn), and the notification worker. In production, run all three under
systemd so they restart on crash and on reboot.

```bash
sudo cp infra/systemd/shivir-bot.service.example /etc/systemd/system/shivir-bot.service
sudo cp infra/systemd/shivir-web.service.example /etc/systemd/system/shivir-web.service
sudo cp infra/systemd/shivir-worker.service.example /etc/systemd/system/shivir-worker.service
# edit the three files if your paths/user differ from /opt/shivir and `shivir`
sudo systemctl daemon-reload
sudo systemctl enable --now shivir-bot shivir-web shivir-worker
sudo systemctl status shivir-bot shivir-web shivir-worker
```

For local development, just run each in its own terminal instead:

```bash
.venv/bin/python -m bot.main
.venv/bin/uvicorn web.main:app --reload --port 8000
.venv/bin/python -m workers.main
```

## 6. Nginx + HTTPS

```bash
sudo cp infra/nginx.conf.example /etc/nginx/sites-available/shivir
sudo ln -s /etc/nginx/sites-available/shivir /etc/nginx/sites-enabled/shivir
# edit server_name to your real domain
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d shivir.example.com   # obtains + wires up the certificate
```

The sender web page must be reachable over HTTPS — it's opened from inside
Instagram's and Telegram's in-app browsers, both of which require it.

## 7. Health checks

`GET /health` actually checks its dependencies (a `SELECT 1` against Postgres,
a `PING` against Redis) rather than just confirming the process is up —
returns `{"status": "ok", "checks": {"database": true, "redis": true}}` with
HTTP 200 when both are reachable, or `{"status": "degraded", ...}` with HTTP
503 the moment either isn't. It's already wired into the Nginx config above
(`location /health`). Point any uptime monitor (UptimeRobot, a simple
cron+curl, etc.) at `https://shivir.example.com/health`.

There's no equivalent single-shot health check for the bot or worker
processes since they don't serve HTTP — use `systemctl status` /
`journalctl -u shivir-bot -u shivir-worker` (see Logs below), or alert on the
Redis notification queue length growing unbounded (`LLEN shivir:notify:queue`)
as a proxy for "the worker has stopped consuming."

## 8. Logs

All three processes log to stdout/stderr, which systemd captures into the
journal:

```bash
journalctl -u shivir-bot -f
journalctl -u shivir-web -f
journalctl -u shivir-worker -f
```

`LOG_LEVEL` in `.env` controls verbosity (`INFO` in production; `DEBUG` only
temporarily while diagnosing something, since it's noisier).

**Log retention (privacy):** the master plan's privacy commitment is "no raw
long-term IP logs." The application itself never writes a raw IP anywhere —
verified directly, not just by design: `core/security.py`'s fingerprint hash
is the only thing derived from it, and that's a one-way HMAC (see
`web/routes/sender.py`'s `client_fingerprint()`). The one place a raw IP
does legitimately exist is Nginx's own access log (standard practice, and
uvicorn's own access log is disabled — see the `--no-access-log` flag in
`infra/systemd/shivir-web.service.example` — specifically so there isn't a
second copy of it). Keep that one copy bounded:

```bash
# /etc/logrotate.d/nginx already exists on most distros; confirm it has a
# retention period, e.g.:
#   /var/log/nginx/*.log {
#       daily
#       rotate 30
#       ...
#   }
```

And cap how long systemd keeps the bot/web/worker journal:

```ini
# /etc/systemd/journald.conf
MaxRetentionSec=30day
```

## 9. Backups and restore

```bash
# One-time: put a plain (non-SQLAlchemy-scheme) Postgres URL where the backup
# script can find it — keep this out of the app's own .env, it's a separate
# credential path used only for pg_dump/pg_restore.
export PG_DUMP_URL="postgresql://shivir:<password>@localhost:5432/shivir"
infra/backup.sh
```

Schedule it nightly via cron (see the comment at the top of `infra/backup.sh`
for the exact line). It keeps 14 days of backups by default.

**Restore:**

```bash
sudo systemctl stop shivir-bot shivir-web shivir-worker
pg_restore --dbname="$PG_DUMP_URL" --clean --if-exists /var/backups/shivir/shivir-<timestamp>.dump
sudo systemctl start shivir-bot shivir-web shivir-worker
```

Test the restore procedure at least once before you need it for real —
an untested backup is not a backup.

## 10. Basic monitoring

V1-appropriate, not the Founder Dashboard (that's V2+):

- Uptime monitor on `/health` (see §7)
- `journalctl` alerts (or a simple log-grep cron) for repeated `ERROR` lines
  from the worker (`Giving up on message ... after 3 attempts` is the one
  worth paging on — it means real notifications are being lost)
- `LLEN shivir:notify:queue` via `redis-cli` — sustained growth means the
  worker is stuck or down
- Disk space on the Postgres data volume (message bodies are the only
  meaningfully-growing table; deleted messages clear their own body text)

## 11. Scaling triggers

Stay on this single-VPS setup until you actually hit one of these (per the
master plan's scaling-trigger guidance) — don't pre-optimize:

- Sustained CPU > 60% or notification-queue lag > 30s (Decision Gate 8)
- Postgres connection count approaching its configured max under real load
- Redis memory approaching its configured maxmemory

When one of those triggers, the next step is a bigger VPS or splitting
Postgres/Redis onto their own host — still not Kubernetes/microservices at
the 10K–50K MAU tier the master plan describes.
