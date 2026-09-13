"""Regression tests for the backup automation (infra/backup.sh +
infra/systemd/shivir-backup.{service,timer}.example): credentials must come
from the app's own .env (no separate PG_DUMP_URL to create/export), the
password must never appear on the pg_dump command line, and the backup must
actually be scheduled (systemd timer), not just documented as a manual step.

Plain text checks, consistent with test_docker_compose_hardening.py — these
are small, static config/shell files with no test runner of their own.
Deeper behavioral verification (does the script actually fail correctly on
a missing .env/password, does it actually keep the password out of argv,
does retention cleanup actually delete old backups) was done by directly
executing infra/backup.sh with a stub pg_dump during development; that's a
one-time manual check, not repeated here, since reliably invoking a bash
script from pytest on Windows (this repo's dev environment) without
Windows/MSYS path-translation flakiness isn't worth the complexity next to
these static checks, and CI (ubuntu-latest) never exercises this file at all
today.
"""

from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[2] / "infra"
BACKUP_SCRIPT = INFRA_DIR / "backup.sh"
BACKUP_SERVICE = INFRA_DIR / "systemd" / "shivir-backup.service.example"
BACKUP_TIMER = INFRA_DIR / "systemd" / "shivir-backup.timer.example"
DEPLOYMENT_DOC = INFRA_DIR / "DEPLOYMENT.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_backup_script_no_longer_requires_separate_credential():
    content = _read(BACKUP_SCRIPT)
    assert "PG_DUMP_URL" not in content


def test_backup_script_reads_password_from_env_file():
    content = _read(BACKUP_SCRIPT)
    assert "ENV_FILE" in content
    assert "POSTGRES_PASSWORD=" in content
    assert 'grep -E' in content


def test_backup_script_grep_failure_does_not_silently_abort():
    """Regression: set -e + pipefail + grep's 'no match' exit code used to
    abort the script before its own explicit, user-facing error message ever
    ran. The `|| true` on that pipeline is what fixes it."""
    content = _read(BACKUP_SCRIPT)
    assert "|| true" in content


def test_backup_script_passes_password_via_env_not_command_line():
    content = _read(BACKUP_SCRIPT)
    assert "PGPASSWORD=" in content
    # The old, insecure pattern: a URL (with credentials) as a pg_dump argument.
    assert "--dbname=\"$PG_DUMP_URL\"" not in content
    assert "--dbname=\"$PG_DATABASE\"" in content


def test_backup_script_fails_loudly_when_password_missing():
    content = _read(BACKUP_SCRIPT)
    assert "exit 1" in content
    assert "not set in" in content


def test_backup_service_example_exists_and_runs_the_script():
    content = _read(BACKUP_SERVICE)
    assert "Type=oneshot" in content
    assert "backup.sh" in content
    assert "ENV_FILE=" in content


def test_backup_service_retention_days_matches_what_deployment_doc_claims():
    """Regression: DEPLOYMENT.md told operators to override retention via
    "RETENTION_DAYS in the service's Environment= lines" while no such line
    actually existed in the file — the documented override point has to be
    real, and its stated value (14) has to match backup.sh's own default."""
    service_content = _read(BACKUP_SERVICE)
    assert "Environment=RETENTION_DAYS=14" in service_content
    assert "RETENTION_DAYS=\"${RETENTION_DAYS:-14}\"" in _read(BACKUP_SCRIPT)


def test_backup_timer_example_runs_daily_and_catches_up_missed_runs():
    content = _read(BACKUP_TIMER)
    assert "OnCalendar=daily" in content
    assert "Persistent=true" in content  # runs a missed backup after downtime
    assert "WantedBy=timers.target" in content


def test_deployment_doc_describes_systemd_timer_not_manual_cron():
    content = _read(DEPLOYMENT_DOC)
    assert "shivir-backup.timer" in content
    assert "export PG_DUMP_URL" not in content  # the old manual-credential step


def test_gitignore_protects_backup_dump_files():
    gitignore = _read(INFRA_DIR.parent / ".gitignore")
    assert "*.dump" in gitignore
