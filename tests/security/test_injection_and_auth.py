"""Security-focused tests: authorization boundaries, forged/invalid tokens,
and markup-injection via sender-controlled content."""

import httpx
from httpx import ASGITransport
from sqlalchemy import select

from core.config import get_settings
from core.models import Message, ModerationAction, User
from core.security import generate_csrf_token, verify_csrf_token
from core.services.links import create_link
from core.services.messages import send_message

from bot.handlers import inbox, moderation
from tests.fakes import FakeCallbackQuery, FakeMessage

settings = get_settings()


async def _seed_message(db_session, fake_redis, recipient_id: int, body: str = "hello"):
    db_session.add(User(tg_user_id=recipient_id))
    await db_session.commit()
    link = await create_link(db_session, owner_user_id=recipient_id)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=recipient_id,
        body=body, fingerprint_hash="fp-sec", acknowledge_warning=True,
    )
    return result.message_id


# --- Authorization: a user cannot open/act on another user's message ---

async def test_cannot_open_another_users_message(db_session, clean_tables, fake_redis):
    message_id = await _seed_message(db_session, fake_redis, 7001)

    attacker_msg = FakeMessage(user_id=7002)  # different Telegram user
    cb = FakeCallbackQuery(user_id=7002, data=f"msg:open:{message_id}", message=attacker_msg)
    await inbox.on_message_open(cb, db_session)

    # No content leaked — the handler answered with a generic error, not the body.
    assert attacker_msg.edited == []
    assert cb.answers[0]["text"] is not None


async def test_cannot_delete_another_users_message(db_session, clean_tables, fake_redis):
    message_id = await _seed_message(db_session, fake_redis, 7003, body="private content")

    attacker_msg = FakeMessage(user_id=7004)
    cb = FakeCallbackQuery(user_id=7004, data=f"msg:deleteconfirm:{message_id}", message=attacker_msg)
    await inbox.on_delete_confirm(cb, db_session)

    stored = await db_session.get(Message, message_id)
    assert stored.body == "private content"  # untouched
    assert stored.deleted_at is None


async def test_moderation_commands_hidden_from_non_admin(db_session, clean_tables):
    non_admin_msg = FakeMessage(user_id=8888)  # not in ADMIN_TG_USER_IDS
    await moderation.cmd_modqueue(non_admin_msg, db_session, settings)
    assert non_admin_msg.sent == []


async def test_moderation_decision_rejected_for_non_admin(db_session, clean_tables):
    action_id = 1
    fake_msg = FakeMessage(user_id=8888)
    cb = FakeCallbackQuery(user_id=8888, data=f"mod:dismiss:{action_id}", message=fake_msg)
    await moderation.on_moderation_decision(cb, db_session, settings)
    # No decision recorded — the handler returned before touching the DB.
    result = await db_session.execute(select(ModerationAction))
    assert result.scalars().first() is None


# --- CSRF / forged tokens ---

def test_csrf_token_rejects_wrong_context():
    token = generate_csrf_token(settings.secret_key, context="link-abc")
    assert verify_csrf_token(settings.secret_key, token, context="link-xyz") is False


def test_csrf_token_rejects_tampered_signature():
    token = generate_csrf_token(settings.secret_key, context="link-abc")
    issued_at, _sig = token.split(".", 1)
    forged = f"{issued_at}.deadbeef" * 4
    assert verify_csrf_token(settings.secret_key, forged, context="link-abc") is False


def test_csrf_token_rejects_expired():
    import time

    token = generate_csrf_token(settings.secret_key, context="link-abc", ttl_seconds=3600)
    # Simulate an old token by moving the issued_at far into the past.
    _, sig = token.split(".", 1)
    old_issued_at = int(time.time()) - 999999
    forged_old = f"{old_issued_at}.{sig}"
    assert verify_csrf_token(settings.secret_key, forged_old, context="link-abc") is False


async def test_send_rejects_csrf_scoped_to_different_link(db_session, clean_tables, fake_redis):
    db_session.add(User(tg_user_id=7010))
    await db_session.commit()
    link_a = await create_link(db_session, owner_user_id=7010)

    db_session.add(User(tg_user_id=7011))
    await db_session.commit()
    link_b = await create_link(db_session, owner_user_id=7011)

    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # CSRF token minted for link_a's page...
        token_for_a = generate_csrf_token(settings.secret_key, context=link_a.token)
        # ...used against link_b's send endpoint.
        resp = await client.post(
            f"/s/{link_b.token}/send",
            json={"message": "hi", "csrf_token": token_for_a},
        )
    assert resp.status_code == 403


# --- Markup injection: sender content must never be parsed as markup ---

async def test_message_detail_rendered_with_no_parse_mode(db_session, clean_tables, fake_redis):
    malicious_body = "[click me](http://evil.example/phish) *bold* `code`"
    message_id = await _seed_message(db_session, fake_redis, 7020, body=malicious_body)

    fake_msg = FakeMessage(user_id=7020)
    cb = FakeCallbackQuery(user_id=7020, data=f"msg:open:{message_id}", message=fake_msg)
    await inbox.on_message_open(cb, db_session)

    call = fake_msg.edited[-1]
    assert call["parse_mode"] is None  # never interpreted as Markdown/HTML
    assert malicious_body in call["text"]  # shown verbatim, not stripped either


async def test_moderation_queue_rendered_with_no_parse_mode(db_session, clean_tables, fake_redis):
    admin_id = next(iter(settings.admin_ids))
    malicious_body = "<a href='http://evil.example'>click</a> seni o'ldiraman"
    await _seed_message(db_session, fake_redis, 7021, body=malicious_body)

    admin_msg = FakeMessage(user_id=admin_id)
    await moderation.cmd_modqueue(admin_msg, db_session, settings)

    assert len(admin_msg.sent) >= 1
    for record in admin_msg.sent:
        assert record["parse_mode"] is None
