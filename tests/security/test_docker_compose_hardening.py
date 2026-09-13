"""Regression tests for infra/docker-compose.yml's production security
requirements: Postgres/Redis must be loopback-only, and the Postgres
password must come from an environment variable, never be hardcoded.

Plain text checks rather than a YAML parse — no need for a new dependency
just to assert on a handful of literal lines in a small, static file.
"""

from pathlib import Path

COMPOSE_PATH = Path(__file__).resolve().parents[2] / "infra" / "docker-compose.yml"


def _read_compose() -> str:
    return COMPOSE_PATH.read_text(encoding="utf-8")


def test_postgres_port_is_bound_to_loopback_only():
    content = _read_compose()
    assert '"127.0.0.1:5432:5432"' in content
    assert '"5432:5432"' not in content  # the old, publicly-exposed form


def test_redis_port_is_bound_to_loopback_only():
    content = _read_compose()
    assert '"127.0.0.1:6379:6379"' in content
    assert '"6379:6379"' not in content  # the old, publicly-exposed form


def test_postgres_password_is_not_hardcoded():
    content = _read_compose()
    assert "POSTGRES_PASSWORD: shivir" not in content  # the old literal value
    assert "${POSTGRES_PASSWORD" in content  # sourced from the environment instead


def test_postgres_password_variable_has_no_silent_blank_fallback():
    """${VAR:-} / ${VAR} with no guard would silently start Postgres with an
    empty password if POSTGRES_PASSWORD is unset. Must use the `:?` form so
    compose refuses to start instead."""
    content = _read_compose()
    assert "${POSTGRES_PASSWORD:?" in content


def test_env_example_documents_a_strong_postgres_password_requirement():
    env_example = (COMPOSE_PATH.parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "POSTGRES_PASSWORD=" in env_example
    assert "strong random" in env_example.lower()
