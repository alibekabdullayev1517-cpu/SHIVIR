"""Integration tests for the sender web experience (FastAPI routes)."""

import httpx
import pytest_asyncio
from httpx import ASGITransport

from core.config import get_settings
from core.models import Message, User
from core.services.links import create_link

settings = get_settings()


@pytest_asyncio.fixture
async def client(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _make_link(db_session, owner_id: int, lang: str = "uz"):
    db_session.add(User(tg_user_id=owner_id, lang=lang))
    await db_session.commit()
    return await create_link(db_session, owner_user_id=owner_id)


async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": True, "redis": True}


async def test_invalid_token_returns_404_generic_message(client):
    resp = await client.get("/s/does-not-exist")
    assert resp.status_code == 404
    assert "faol emas" in resp.text  # never leaks *why* it's invalid


async def test_valid_link_renders_compose_page(client, db_session, clean_tables):
    link = await _make_link(db_session, 2001)
    resp = await client.get(f"/s/{link.token}")
    assert resp.status_code == 200
    assert "composer" in resp.text
    assert 'id="sendButton"' in resp.text


async def _get_csrf_token(resp_text: str) -> str:
    import re

    match = re.search(r'const csrfToken = "([^"]+)"', resp_text)
    assert match, "csrf token not found in page"
    return match.group(1)


async def test_send_clean_message_succeeds(client, db_session, clean_tables):
    link = await _make_link(db_session, 2002)
    page = await client.get(f"/s/{link.token}")
    csrf = await _get_csrf_token(page.text)

    resp = await client.post(
        f"/s/{link.token}/send",
        json={"message": "Ishlaring qalay, hammasi joyidami?", "csrf_token": csrf},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"

    from sqlalchemy import select

    result = await db_session.execute(select(Message).where(Message.link_id == link.id))
    stored = result.scalars().first()
    assert stored is not None
    assert stored.body == "Ishlaring qalay, hammasi joyidami?"


async def test_send_without_valid_csrf_is_rejected(client, db_session, clean_tables):
    link = await _make_link(db_session, 2003)
    resp = await client.post(
        f"/s/{link.token}/send", json={"message": "hello", "csrf_token": "forged.token"}
    )
    assert resp.status_code == 403


async def test_send_empty_message_is_rejected(client, db_session, clean_tables):
    link = await _make_link(db_session, 2004)
    page = await client.get(f"/s/{link.token}")
    csrf = await _get_csrf_token(page.text)

    resp = await client.post(f"/s/{link.token}/send", json={"message": "   ", "csrf_token": csrf})
    assert resp.status_code == 422


async def test_rate_limited_send_returns_429(client, db_session, clean_tables):
    link = await _make_link(db_session, 2010)
    page = await client.get(f"/s/{link.token}")
    csrf = await _get_csrf_token(page.text)

    original_limit = settings.rate_limit_send_per_fingerprint
    settings.rate_limit_send_per_fingerprint = 1
    try:
        first = await client.post(
            f"/s/{link.token}/send", json={"message": "salom", "csrf_token": csrf}
        )
        assert first.status_code == 200

        second = await client.post(
            f"/s/{link.token}/send", json={"message": "salom yana", "csrf_token": csrf}
        )
        assert second.status_code == 429
        assert second.json()["status"] == "rate_limited"
    finally:
        settings.rate_limit_send_per_fingerprint = original_limit


async def test_send_abusive_message_needs_warning_then_can_be_acknowledged(client, db_session, clean_tables):
    link = await _make_link(db_session, 2005)
    page = await client.get(f"/s/{link.token}")
    csrf = await _get_csrf_token(page.text)

    first = await client.post(
        f"/s/{link.token}/send", json={"message": "seni o'ldiraman", "csrf_token": csrf}
    )
    assert first.json()["status"] == "needs_warning"
    assert first.json()["category"] == "threat"

    from sqlalchemy import select

    result = await db_session.execute(select(Message).where(Message.link_id == link.id))
    assert result.scalars().first() is None  # not stored yet

    second = await client.post(
        f"/s/{link.token}/send",
        json={"message": "seni o'ldiraman", "csrf_token": csrf, "acknowledge_warning": True},
    )
    assert second.json()["status"] == "success"


async def test_send_to_invalid_link_returns_invalid_status(client, db_session, clean_tables):
    resp = await client.post(
        "/s/nonexistent-token/send", json={"message": "hi", "csrf_token": "x"}
    )
    assert resp.status_code == 403  # CSRF check fails first, which is correct: no info leak either way


async def test_message_started_beacon_records_event(client, db_session, clean_tables):
    from sqlalchemy import select

    from core.models import Event

    link = await _make_link(db_session, 2006)
    resp = await client.post(f"/s/{link.token}/track", json={"name": "message_started"})
    assert resp.status_code == 200

    result = await db_session.execute(select(Event).where(Event.name == "message_started"))
    assert result.scalars().first() is not None


async def test_message_started_beacon_ignores_unknown_events(client, db_session, clean_tables):
    from sqlalchemy import select

    from core.models import Event

    link = await _make_link(db_session, 2007)
    resp = await client.post(f"/s/{link.token}/track", json={"name": "something_else"})
    assert resp.json()["status"] == "ignored"

    result = await db_session.execute(select(Event).where(Event.name == "something_else"))
    assert result.scalars().first() is None


# --- P2: /track must fail safe on malformed/empty telemetry, never a 500 ---


async def test_track_malformed_json_body_is_ignored_not_500(client, db_session, clean_tables):
    link = await _make_link(db_session, 2008)
    resp = await client.post(
        f"/s/{link.token}/track",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


async def test_track_empty_body_is_ignored_not_500(client, db_session, clean_tables):
    link = await _make_link(db_session, 2009)
    resp = await client.post(
        f"/s/{link.token}/track",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


async def test_track_valid_json_non_object_is_ignored_not_500(client, db_session, clean_tables):
    """Valid JSON that isn't an object (e.g. a bare array) has no .get() —
    must be treated as ignored, not crash on the attribute access."""
    link = await _make_link(db_session, 2010)
    resp = await client.post(
        f"/s/{link.token}/track",
        content=b"[1, 2, 3]",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


async def test_track_valid_message_started_event_still_recorded_after_fix(client, db_session, clean_tables):
    """The fail-safe handling above must not weaken the legitimate path."""
    from sqlalchemy import select

    from core.models import Event

    link = await _make_link(db_session, 2011)
    resp = await client.post(f"/s/{link.token}/track", json={"name": "message_started"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    result = await db_session.execute(select(Event).where(Event.name == "message_started"))
    assert result.scalars().first() is not None
