"""Shared test fixtures.

Tests run against a throwaway file-based SQLite database (via aiosqlite) and a
fakeredis in-memory Redis, so the full suite needs zero live infrastructure.
Environment variables MUST be set before any `core.*` module is imported for the
first time in the process, because `core.db` builds its engine at import time.
"""

import os
import tempfile
from pathlib import Path

_tmp_db = Path(tempfile.gettempdir()) / "shivir_test.db"
if _tmp_db.exists():
    _tmp_db.unlink()

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("BOT_TOKEN", "123456:test-token")
os.environ.setdefault("BOT_USERNAME", "shivir_test_bot")
os.environ.setdefault("WEB_BASE_URL", "http://testserver")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_tmp_db.as_posix()}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("ADMIN_TG_USER_IDS", "999999999")

import pytest
import pytest_asyncio
import fakeredis.aioredis

from core.config import get_settings
from core.db import SessionLocal, engine
from core.models import Base

get_settings.cache_clear()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def clean_tables(db_session):
    """Truncate all tables between tests that need isolation."""
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(table.delete())
    await db_session.commit()
    yield


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)
