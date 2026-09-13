import json
from datetime import datetime, timedelta, timezone

from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from core.models import Message, User
from core.services.links import create_link
from core.services.messages import NOTIFICATION_QUEUE_KEY, send_message
from tests.fakes import FakeBot
from workers import notifier

from core.config import get_settings

settings = get_settings()


async def _enqueue_clean_message(db_session, fake_redis, recipient_id: int) -> int:
    db_session.add(User(tg_user_id=recipient_id, lang="uz"))
    await db_session.commit()
    link = await create_link(db_session, owner_user_id=recipient_id)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=recipient_id,
        body="Salom!", fingerprint_hash="fp-notif",
    )
    return result.message_id


async def test_successful_delivery_sets_notified_at(db_session, clean_tables, fake_redis):
    message_id = await _enqueue_clean_message(db_session, fake_redis, 4001)
    bot = FakeBot()

    delivered = await notifier.process_one(bot, db_session, fake_redis, timeout=1)

    assert delivered is True
    assert len(bot.sent) == 1
    assert bot.sent[0]["chat_id"] == 4001

    message = await db_session.get(Message, message_id)
    assert message.notified_at is not None


async def test_empty_queue_returns_false(db_session, fake_redis):
    delivered = await notifier.process_one(FakeBot(), db_session, fake_redis, timeout=1)
    assert delivered is False


async def test_deleted_message_is_skipped(db_session, clean_tables, fake_redis):
    message_id = await _enqueue_clean_message(db_session, fake_redis, 4002)
    message = await db_session.get(Message, message_id)
    message.body = ""
    from datetime import datetime, timezone
    message.deleted_at = datetime.now(timezone.utc)
    await db_session.commit()

    bot = FakeBot()
    await notifier.process_one(bot, db_session, fake_redis, timeout=1)

    assert bot.sent == []


async def test_forbidden_error_marks_blocked_and_does_not_retry(db_session, clean_tables, fake_redis, monkeypatch):
    await _enqueue_clean_message(db_session, fake_redis, 4003)
    bot = FakeBot(side_effects=[TelegramForbiddenError(method=None, message="blocked")])

    await notifier.process_one(bot, db_session, fake_redis, timeout=1)

    user = await db_session.get(User, 4003)
    assert user.blocked_bot is True
    assert bot.sent == []


async def test_retry_after_then_success(db_session, clean_tables, fake_redis):
    message_id = await _enqueue_clean_message(db_session, fake_redis, 4004)
    bot = FakeBot(side_effects=[TelegramRetryAfter(method=None, message="slow down", retry_after=0)])

    await notifier.process_one(bot, db_session, fake_redis, timeout=1)

    assert len(bot.sent) == 1
    message = await db_session.get(Message, message_id)
    assert message.notified_at is not None


async def test_gives_up_after_max_attempts(db_session, clean_tables, fake_redis, monkeypatch):
    monkeypatch.setattr(notifier, "BASE_BACKOFF_SECONDS", 0)
    await _enqueue_clean_message(db_session, fake_redis, 4005)
    bot = FakeBot(side_effects=[RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom")])

    await notifier.process_one(bot, db_session, fake_redis, timeout=1)

    assert bot.sent == []  # never succeeded, but the worker didn't crash either


async def _make_message_without_enqueueing(db_session, recipient_id: int, age_seconds: int) -> int:
    """Creates a stored, un-notified message directly (bypassing send_message,
    so it's never pushed to the Redis queue) — simulates a queue entry lost to
    a Redis restart/eviction."""
    db_session.add(User(tg_user_id=recipient_id))
    await db_session.commit()
    link = await create_link(db_session, owner_user_id=recipient_id)
    message = Message(
        link_id=link.id,
        recipient_user_id=recipient_id,
        body="lost notification",
        sender_fingerprint_hash="fp-lost",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)
    return message.id


async def test_recover_stale_messages_requeues_lost_notification(db_session, clean_tables, fake_redis):
    message_id = await _make_message_without_enqueueing(db_session, 4006, age_seconds=300)

    recovered = await notifier.recover_stale_messages(db_session, fake_redis)

    assert recovered == 1
    queued = await fake_redis.lrange(NOTIFICATION_QUEUE_KEY, 0, -1)
    assert json.loads(queued[0])["message_id"] == message_id


async def test_recover_stale_messages_ignores_recent_messages(db_session, clean_tables, fake_redis):
    await _make_message_without_enqueueing(db_session, 4007, age_seconds=5)

    recovered = await notifier.recover_stale_messages(db_session, fake_redis)

    assert recovered == 0
    assert await fake_redis.llen(NOTIFICATION_QUEUE_KEY) == 0


async def test_recover_stale_messages_ignores_already_notified(db_session, clean_tables, fake_redis):
    message_id = await _make_message_without_enqueueing(db_session, 4008, age_seconds=300)
    message = await db_session.get(Message, message_id)
    message.notified_at = datetime.now(timezone.utc)
    await db_session.commit()

    recovered = await notifier.recover_stale_messages(db_session, fake_redis)

    assert recovered == 0


async def test_recover_stale_messages_ignores_deleted(db_session, clean_tables, fake_redis):
    message_id = await _make_message_without_enqueueing(db_session, 4009, age_seconds=300)
    message = await db_session.get(Message, message_id)
    message.deleted_at = datetime.now(timezone.utc)
    message.body = ""
    await db_session.commit()

    recovered = await notifier.recover_stale_messages(db_session, fake_redis)

    assert recovered == 0
