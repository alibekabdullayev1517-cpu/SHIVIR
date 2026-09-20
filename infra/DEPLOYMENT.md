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
- `DATABASE_URL` — `postgresql+asyncpg://shivir:<same password as POSTGRES_PASSWORD>@localhost:5432/shivir` to bootstrap with (the full superuser — fine for initial setup and running migrations). **Before going live, switch the running app to the least-privilege `shivir_app` role instead — see §5.**
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

(This works as-is only while `DATABASE_URL` still points at the `shivir`
superuser, i.e. before applying §5. Once the app has been switched to the
least-privilege `shivir_app` role, migrations need `ALEMBIC_DATABASE_URL`
set explicitly — see §5 — or they will correctly fail with a permission
error rather than silently doing nothing.)

## 5. Least-privilege database role (production hardening)

Sections 3–4 get the app running fastest with the Postgres superuser
(`shivir`) for everything — fine to bootstrap with, but the three running
app services shouldn't keep using it afterward. In production they connect
as a separate, deliberately unprivileged role instead. This is a real
credential-and-privilege change, not a cosmetic one — read this whole
section, and verify each step against a scratch database first, before
touching the production role or `.env`.

**Three separate credential paths, by design:**

- **Runtime app** (`shivir-web`/`shivir-bot`/`shivir-worker`) — `.env`'s
  `DATABASE_URL` uses `shivir_app`: `SELECT`/`INSERT`/`UPDATE` on the app's
  own 7 tables only. No `DELETE`, no DDL (`CREATE`/`ALTER`/`DROP`), no
  `TRUNCATE`, no `COPY`, no superuser/`CREATEDB`/`CREATEROLE`/replication/
  `BYPASSRLS`, and — deliberately — no access at all to `alembic_version`.
- **Alembic migrations** — need real DDL, which `shivir_app` cannot do by
  design. `migrations/env.py` checks an **`ALEMBIC_DATABASE_URL`**
  environment variable first, falling back to `.env`'s `DATABASE_URL` only
  if that's unset:

  ```bash
  ALEMBIC_DATABASE_URL="postgresql+asyncpg://shivir:<POSTGRES_PASSWORD>@localhost:5432/shivir" \
    .venv/bin/alembic upgrade head
  ```

  **Verify this is set correctly before every migration run** — check the
  role it points at actually has DDL rights (`shivir`, not `shivir_app`)
  before you run `upgrade`/`downgrade` for real. If you forget the
  override entirely, Alembic now fails loudly (`permission denied for
  table alembic_version`) instead of silently doing nothing — a safe
  failure, but still worth not tripping over.
- **Backups** (`infra/backup.sh`) — unaffected by any of this. It never
  reads `DATABASE_URL`; it reads `POSTGRES_PASSWORD` directly out of `.env`
  and always connects as `shivir` (see §10). Nothing to change here.

**One-time role setup**, run as the `shivir` superuser (`psql -U shivir -d shivir`):

```sql
CREATE ROLE shivir_app WITH LOGIN PASSWORD '<generate a new strong password>'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

GRANT CONNECT ON DATABASE shivir TO shivir_app;
GRANT USAGE ON SCHEMA public TO shivir_app;

GRANT SELECT, INSERT, UPDATE ON public.users, public.public_links, public.messages TO shivir_app;
GRANT SELECT, INSERT ON public.blocks, public.reports, public.moderation_actions, public.events TO shivir_app;
-- Deliberately no grant at all on alembic_version — the app never touches it.

GRANT USAGE, SELECT ON SEQUENCE
    public.public_links_id_seq, public.messages_id_seq, public.blocks_id_seq,
    public.reports_id_seq, public.moderation_actions_id_seq, public.events_id_seq,
    public.users_tg_user_id_seq
    TO shivir_app;
```

Then, only after verifying the grants above against a scratch database and
confirming the app's real read/write paths still work end-to-end:

1. Update `.env`'s `DATABASE_URL` to use `shivir_app` and the new password.
2. `sudo systemctl restart shivir-web shivir-bot shivir-worker`.
3. Verify: `/health` still green, logs clean (no permission-denied
   errors), a real send/read still works.

Confirm the resulting grants at any time with:

```sql
SELECT table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) AS privs
FROM information_schema.role_table_grants
WHERE grantee = 'shivir_app' GROUP BY table_name ORDER BY table_name;
```

**Never put production secrets — the `shivir_app` password, `POSTGRES_PASSWORD`,
`DATABASE_URL`, `BOT_TOKEN`, `SECRET_KEY`, anything from `.env` — in git.**
`.env` is gitignored for exactly this reason; every credential above is
generated once, by hand, on the server, and lives only in `.env` (mode 600)
and the Postgres role itself.

## 6. Running the three processes

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

## 7. Nginx + HTTPS

```bash
sudo cp infra/nginx.conf.example /etc/nginx/sites-available/shivir
sudo ln -s /etc/nginx/sites-available/shivir /etc/nginx/sites-enabled/shivir
# edit server_name to your real domain
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d shivir.example.com   # obtains + wires up the certificate
```

The sender web page must be reachable over HTTPS — it's opened from inside
Instagram's and Telegram's in-app browsers, both of which require it.

## 8. Health checks

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

## 9. Logs

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
#       rotate 14
#       ...
#   }
```

**Keep the public privacy page true.** `web/routes/legal.py` tells users that raw
IPs in web-server logs, and deleted-message text in daily backups, are kept for
"about two weeks". That matches `rotate 14` above and `RETENTION_DAYS=14` in
`infra/backup.sh`. If you change either number, change the privacy page (uz + ru) too.

And cap how long systemd keeps the bot/web/worker journal:

```ini
# /etc/systemd/journald.conf
MaxRetentionSec=30day
```

## 10. Backups and restore

`infra/backup.sh` reads `POSTGRES_PASSWORD` directly out of the app's own
`.env` (just that one variable — never the whole file) and passes it to
`pg_dump` via the `PGPASSWORD` environment variable rather than embedding it
in a connection URL, so it never shows up in `ps aux` output. No separate
credential to create or keep in sync with `.env`.

Automated daily via a systemd timer rather than cron:

```bash
sudo cp infra/systemd/shivir-backup.service.example /etc/systemd/system/shivir-backup.service
sudo cp infra/systemd/shivir-backup.timer.example /etc/systemd/system/shivir-backup.timer
# edit shivir-backup.service if your paths/user differ from /opt/shivir and `shivir`
sudo mkdir -p /var/backups/shivir && sudo chown shivir:shivir /var/backups/shivir
sudo systemctl daemon-reload
sudo systemctl enable --now shivir-backup.timer
systemctl list-timers shivir-backup.timer   # confirm it's scheduled
```

Run it once by hand to confirm it actually works before trusting the timer:

```bash
sudo systemctl start shivir-backup.service
journalctl -u shivir-backup.service -n 20
```

It keeps 14 days of backups by default (`RETENTION_DAYS` in the service's
`Environment=` lines, or override there).

**Restore:**

```bash
sudo systemctl stop shivir-bot shivir-web shivir-worker
PGPASSWORD="$(grep -E '^POSTGRES_PASSWORD=' /opt/shivir/.env | tail -n1 | cut -d '=' -f2-)" \
  pg_restore --host=localhost --port=5432 --username=shivir --dbname=shivir \
  --clean --if-exists /var/backups/shivir/shivir-<timestamp>.dump
sudo systemctl start shivir-bot shivir-web shivir-worker
```

Test the restore procedure at least once before you need it for real —
an untested backup is not a backup.

## 11. Basic monitoring

V1-appropriate, not the Founder Dashboard (that's V2+):

- Uptime monitor on `/health` (see §8)
- `journalctl` alerts (or a simple log-grep cron) for repeated `ERROR` lines
  from the worker (`Giving up on message ... after 3 attempts` is the one
  worth paging on — it means real notifications are being lost)
- `LLEN shivir:notify:queue` via `redis-cli` — sustained growth means the
  worker is stuck or down
- Disk space on the Postgres data volume (message bodies are the only
  meaningfully-growing table; deleted messages clear their own body text)

## 12. Scaling triggers

Stay on this single-VPS setup until you actually hit one of these (per the
master plan's scaling-trigger guidance) — don't pre-optimize:

- Sustained CPU > 60% or notification-queue lag > 30s (Decision Gate 8)
- Postgres connection count approaching its configured max under real load
- Redis memory approaching its configured maxmemory

When one of those triggers, the next step is a bigger VPS or splitting
Postgres/Redis onto their own host — still not Kubernetes/microservices at
the 10K–50K MAU tier the master plan describes.
