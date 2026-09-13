"""Async SQLAlchemy engine/session wiring."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import get_settings


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_async_engine(url, echo=False, connect_args=connect_args)

    if url.startswith("sqlite"):
        # SQLite does not enforce foreign keys by default (unlike Postgres,
        # our production target) — without this, a broken FK relationship
        # (e.g. an events row referencing a users row that doesn't exist yet)
        # would silently succeed in tests and only fail for real in
        # production. Must be set per-connection, not once per engine.
        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


_settings = get_settings()
engine = _make_engine(_settings.database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency / aiogram middleware session provider."""
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager form for use outside FastAPI's DI (bot handlers, workers)."""
    async with SessionLocal() as session:
        yield session
