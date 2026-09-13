"""Notification worker: consumes the Redis queue `send_message` enqueues into
and delivers genuine (never fake/batched-for-show) Telegram notifications.

Retry behavior:
- TelegramRetryAfter (Telegram's own rate-limit signal) -> sleep exactly as
  told, then retry the same message.
- TelegramForbiddenError (user blocked the bot) -> mark it, drop the message,
  no retry (retrying is pointless and would loop forever).
- Any other transient error -> up to MAX_ATTEMPTS with exponential backoff,
  then drop with a logged error (never silently lose the loop itself over one
  bad message).
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.analytics import track
from core.copy import t
from core.models import Message, User
from core.services.messages import NOTIFICATION_QUEUE_KEY

logger = logging.getLogger("shivir.worker")

MAX_ATTEMPTS = 3
BASE_BACKOFF_SECONDS = 2
# Stays comfortably under Telegram's ~30 msg/sec global send limit.
THROTTLE_SECONDS = 0.05

# The Redis queue is not durable across a Redis restart/eviction between RDB
# snapshots — a queued-but-unpopped entry can simply vanish, silently losing
# a genuine notification with no retry, which would fail the master plan's
# "reliable retry behavior" requirement. This periodic sweep is the backstop:
# any message old enough that it should have been delivered by now, but
# wasn't, gets re-enqueued from Postgres (the durable source of truth).
SWEEP_INTERVAL_SECONDS = 60
STALE_AFTER_SECONDS = 120


async def _deliver(bot: Bot, session: AsyncSession, message_id: int) -> None:
    message = await session.get(Message, message_id)
    if message is None or message.deleted_at is not None:
        return  # deleted (including L3 auto-remove) before we got to it

    recipient = await session.get(User, message.recipient_user_id)
    if recipient is None:
        return

    text = t("new_message_notification", recipient.lang)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            await bot.send_message(chat_id=recipient.tg_user_id, text=text)
            message.notified_at = message.notified_at or datetime.now(timezone.utc)
            await session.commit()
            await track("message_received", user_id=recipient.tg_user_id, message_id=message.id)
            return
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
        except TelegramForbiddenError:
            recipient.blocked_bot = True
            await session.commit()
            # No Telegram user ID in the log line — that's a real identifier
            # tied to a person, and message_id is enough to correlate via the
            # DB if this ever needs investigating.
            logger.info("Recipient has blocked the bot; dropping notification for message %s.", message_id)
            return
        except Exception:
            logger.exception("Delivery attempt %s/%s failed for message %s", attempt, MAX_ATTEMPTS, message_id)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    logger.error("Giving up on message %s after %s attempts.", message_id, MAX_ATTEMPTS)


async def process_one(bot: Bot, session: AsyncSession, redis: Redis, timeout: int = 5) -> bool:
    """Pops and processes a single queued notification. Returns False if the
    queue was empty for the whole `timeout` (caller decides whether to loop)."""
    item = await redis.blpop(NOTIFICATION_QUEUE_KEY, timeout=timeout)
    if item is None:
        return False

    _, raw = item
    payload = json.loads(raw)
    await _deliver(bot, session, payload["message_id"])
    await asyncio.sleep(THROTTLE_SECONDS)
    return True


async def recover_stale_messages(session: AsyncSession, redis: Redis) -> int:
    """Re-enqueues any message that's old enough to have been delivered
    already but wasn't — the backstop for a Redis queue entry lost to a
    restart/eviction. Postgres (notified_at) is the durable source of truth;
    Redis is just the low-latency delivery signal."""
    threshold = datetime.now(timezone.utc) - timedelta(seconds=STALE_AFTER_SECONDS)
    result = await session.execute(
        select(Message.id).where(
            Message.notified_at.is_(None),
            Message.deleted_at.is_(None),
            Message.created_at < threshold,
        )
    )
    ids = [row[0] for row in result.all()]
    for message_id in ids:
        await redis.rpush(NOTIFICATION_QUEUE_KEY, json.dumps({"message_id": message_id}))
    return len(ids)


async def run_forever(bot: Bot, session_factory, redis: Redis) -> None:
    logger.info("Notification worker started.")
    last_sweep = 0.0
    while True:
        async with session_factory() as session:
            await process_one(bot, session, redis)

            now = time.monotonic()
            if now - last_sweep >= SWEEP_INTERVAL_SECONDS:
                recovered = await recover_stale_messages(session, redis)
                if recovered:
                    logger.warning(
                        "Recovered %s stale un-notified message(s) — likely a lost Redis queue entry.",
                        recovered,
                    )
                last_sweep = now
