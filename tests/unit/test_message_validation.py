from core.config import get_settings
from core.models import Block, Message, User
from core.services.links import create_link
from core.services.messages import SendStatus, send_message

settings = get_settings()


async def _make_link(db_session, owner_id: int):
    db_session.add(User(tg_user_id=owner_id))
    await db_session.commit()
    return await create_link(db_session, owner_user_id=owner_id)


async def test_rejects_empty_message(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 10)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=10,
        body="   ", fingerprint_hash="fp",
    )
    assert result.status == SendStatus.EMPTY_MESSAGE


async def test_rejects_too_long_message(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 11)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=11,
        body="x" * 501, fingerprint_hash="fp",
    )
    assert result.status == SendStatus.TOO_LONG


async def test_rejects_inactive_link(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 12)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=False, recipient_user_id=12,
        body="hello", fingerprint_hash="fp",
    )
    assert result.status == SendStatus.INVALID_LINK


async def test_clean_message_is_stored(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 13)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=13,
        body="Ishlaring qalay, hammasi zo'rmi?", fingerprint_hash="fp-clean",
    )
    assert result.status == SendStatus.STORED
    stored = await db_session.get(Message, result.message_id)
    assert stored.body == "Ishlaring qalay, hammasi zo'rmi?"
    assert stored.deleted_at is None


async def test_abusive_message_needs_warning_before_storing(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 14)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=14,
        body="seni o'ldiraman", fingerprint_hash="fp-threat",
    )
    assert result.status == SendStatus.NEEDS_WARNING
    assert result.warning_category == "threat"
    assert result.message_id is None  # not stored yet


async def test_acknowledged_threat_is_stored_but_auto_removed_l3(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 15)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=15,
        body="seni o'ldiraman", fingerprint_hash="fp-threat2",
        acknowledge_warning=True,
    )
    assert result.status == SendStatus.STORED
    stored = await db_session.get(Message, result.message_id)
    # Auto-removed from the recipient's view pending human review (L3).
    assert stored.body == ""
    assert stored.deleted_at is not None


async def test_blocked_sender_is_silently_dropped(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 16)
    db_session.add(Block(user_id=16, sender_fingerprint_hash="fp-blocked"))
    await db_session.commit()

    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=16,
        body="hello there", fingerprint_hash="fp-blocked",
    )
    assert result.status == SendStatus.BLOCKED_SILENT
    assert result.message_id is None


async def test_rate_limit_enforced(db_session, clean_tables, fake_redis):
    link = await _make_link(db_session, 17)
    settings.rate_limit_send_per_fingerprint = 1
    try:
        first = await send_message(
            db_session, fake_redis, settings,
            link_id=link.id, link_active=link.active, recipient_user_id=17,
            body="first message", fingerprint_hash="fp-rl",
        )
        assert first.status == SendStatus.STORED

        second = await send_message(
            db_session, fake_redis, settings,
            link_id=link.id, link_active=link.active, recipient_user_id=17,
            body="second message", fingerprint_hash="fp-rl",
        )
        assert second.status == SendStatus.RATE_LIMITED
        assert second.rate_limit_scope == "fingerprint"
    finally:
        settings.rate_limit_send_per_fingerprint = 5
