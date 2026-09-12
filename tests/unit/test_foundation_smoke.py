"""Smoke test: schema creates and a row round-trips. Confirms Phase 0/1 foundation."""

from core.models import User


async def test_create_and_read_user(db_session, clean_tables):
    user = User(tg_user_id=42, lang="uz")
    db_session.add(user)
    await db_session.commit()

    fetched = await db_session.get(User, 42)
    assert fetched is not None
    assert fetched.lang == "uz"
    assert fetched.blocked_bot is False
