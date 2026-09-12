"""Abuse/red-team scenarios: spam flood, malformed payloads, SQL-injection-
shaped input, mass reporting, and repeated attempts from a blocked sender."""

import httpx
from httpx import ASGITransport
from sqlalchemy import select

from core.config import get_settings
from core.models import Message, User
from core.security import generate_csrf_token
from core.services.links import create_link
from core.services.messages import SendStatus, send_message

settings = get_settings()


async def _make_link(db_session, owner_id: int):
    db_session.add(User(tg_user_id=owner_id))
    await db_session.commit()
    return await create_link(db_session, owner_user_id=owner_id)


async def test_spam_flood_is_capped_by_rate_limit(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 9001)
    original_limit = settings.rate_limit_send_per_fingerprint
    settings.rate_limit_send_per_fingerprint = 3
    try:
        outcomes = []
        for i in range(10):
            result = await send_message(
                db_session, fake_redis, settings,
                link_id=link.id, link_active=link.active, recipient_user_id=9001,
                body=f"message {i}", fingerprint_hash="fp-flood",
            )
            outcomes.append(result.status)

        stored_count = outcomes.count(SendStatus.STORED)
        rate_limited_count = outcomes.count(SendStatus.RATE_LIMITED)
        assert stored_count == 3
        assert rate_limited_count == 7
    finally:
        settings.rate_limit_send_per_fingerprint = original_limit


async def test_repeated_identical_payload_bounded_by_rate_limit_not_infinitely_repeatable(
    db_session, clean_tables, fake_redis
):
    """A 'replay' of the exact same request body is bounded the same way any
    other flood is — by the fingerprint rate limit, not by request identity."""
    link = await _make_link(db_session, 9002)
    original_limit = settings.rate_limit_send_per_fingerprint
    settings.rate_limit_send_per_fingerprint = 2
    try:
        results = [
            await send_message(
                db_session, fake_redis, settings,
                link_id=link.id, link_active=link.active, recipient_user_id=9002,
                body="identical replayed message", fingerprint_hash="fp-replay",
            )
            for _ in range(5)
        ]
        assert sum(1 for r in results if r.status == SendStatus.STORED) == 2
    finally:
        settings.rate_limit_send_per_fingerprint = original_limit


async def test_sql_injection_shaped_message_is_stored_inert_as_text(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 9003)
    payload = "'; DROP TABLE messages; --"

    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=9003,
        body=payload, fingerprint_hash="fp-sqli",
    )
    assert result.status == SendStatus.STORED

    stored = await db_session.get(Message, result.message_id)
    assert stored.body == payload  # stored verbatim as inert text, table still exists

    # The table is provably intact: this SELECT would fail if it had been dropped.
    check = await db_session.execute(select(Message).limit(1))
    assert check is not None


async def test_malformed_json_payload_returns_422_not_500(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/s/some-token/send",
            content=b"{not valid json",
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 422


async def test_oversized_message_field_rejected_before_hitting_db(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 9004)
    page_url_token = link.token

    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        csrf = generate_csrf_token(settings.secret_key, context=page_url_token)
        huge_payload = "x" * 100_000
        resp = await client.post(
            f"/s/{page_url_token}/send",
            json={"message": huge_payload, "csrf_token": csrf},
        )
    assert resp.status_code == 422  # pydantic max_length rejects it, never reaches send_message


async def test_mass_reporting_disables_link_and_does_not_crash(db_session, clean_tables, fake_redis):
    from core.services.moderation import report_message

    link = await _make_link(db_session, 9005)
    message_ids = []
    for i in range(6):
        result = await send_message(
            db_session, fake_redis, settings,
            link_id=link.id, link_active=link.active, recipient_user_id=9005,
            body=f"msg {i}", fingerprint_hash=f"fp-{i}",
        )
        message_ids.append(result.message_id)

    for mid in message_ids:
        message = await db_session.get(Message, mid)
        await report_message(db_session, message, "spam", auto_disable_threshold=5)

    await db_session.refresh(link)
    assert link.active is False


async def test_blocked_sender_repeated_attempts_all_silently_dropped(db_session, clean_tables, fake_redis):
    from core.services.moderation import block_sender

    link = await _make_link(db_session, 9006)
    await block_sender(db_session, 9006, "fp-blocked-repeat")

    for _ in range(5):
        result = await send_message(
            db_session, fake_redis, settings,
            link_id=link.id, link_active=link.active, recipient_user_id=9006,
            body="please let me through", fingerprint_hash="fp-blocked-repeat",
        )
        assert result.status == SendStatus.BLOCKED_SILENT

    count = await db_session.execute(select(Message).where(Message.link_id == link.id))
    assert len(count.scalars().all()) == 0  # nothing was ever stored
