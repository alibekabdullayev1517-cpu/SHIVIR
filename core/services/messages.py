"""The send pipeline: validate -> block-check -> rate-limit -> abuse-filter ->
store -> enqueue notification. This is the single place that orchestrates it,
used by the sender web route.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.models import Block, ModerationAction, Message, Report
from core.rate_limit import check_send_rate_limits
from core.safety.filter import Category, Severity, analyze

MAX_MESSAGE_LENGTH = 500
NOTIFICATION_QUEUE_KEY = "shivir:notify:queue"


class SendStatus(str, Enum):
    INVALID_LINK = "invalid_link"
    EMPTY_MESSAGE = "empty_message"
    TOO_LONG = "too_long"
    BLOCKED_SILENT = "blocked_silent"
    RATE_LIMITED = "rate_limited"
    NEEDS_WARNING = "needs_warning"
    STORED = "stored"


@dataclass
class SendResult:
    status: SendStatus
    rate_limit_scope: str | None = None
    warning_category: str | None = None
    message_id: int | None = None


async def _is_blocked(session: AsyncSession, recipient_user_id: int, fingerprint_hash: str) -> bool:
    result = await session.execute(
        select(Block).where(
            Block.user_id == recipient_user_id,
            Block.sender_fingerprint_hash == fingerprint_hash,
        )
    )
    return result.scalars().first() is not None


async def _enqueue_notification(redis: Redis, message_id: int) -> None:
    await redis.rpush(NOTIFICATION_QUEUE_KEY, json.dumps({"message_id": message_id}))


async def send_message(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    link_id: int,
    link_active: bool,
    recipient_user_id: int,
    body: str,
    fingerprint_hash: str,
    acknowledge_warning: bool = False,
) -> SendResult:
    body = body.strip()

    if not link_active:
        return SendResult(status=SendStatus.INVALID_LINK)
    if not body:
        return SendResult(status=SendStatus.EMPTY_MESSAGE)
    if len(body) > MAX_MESSAGE_LENGTH:
        return SendResult(status=SendStatus.TOO_LONG)

    if await _is_blocked(session, recipient_user_id, fingerprint_hash):
        # Per spec: silently dropped, sender sees a normal success screen.
        return SendResult(status=SendStatus.BLOCKED_SILENT)

    rl = await check_send_rate_limits(
        redis,
        fingerprint_hash=fingerprint_hash,
        link_id=link_id,
        per_fingerprint_limit=settings.rate_limit_send_per_fingerprint,
        per_fingerprint_window=settings.rate_limit_send_per_fingerprint_window_seconds,
        per_link_limit=settings.rate_limit_send_per_link,
        per_link_window=settings.rate_limit_send_per_link_window_seconds,
        global_limit=settings.rate_limit_send_global,
        global_window=settings.rate_limit_send_global_window_seconds,
    )
    if not rl.allowed:
        return SendResult(status=SendStatus.RATE_LIMITED, rate_limit_scope=rl.scope)

    filter_result = analyze(body)
    if filter_result.should_warn and not acknowledge_warning:
        category = filter_result.top_category
        return SendResult(
            status=SendStatus.NEEDS_WARNING,
            warning_category=category.value if category else None,
        )

    message = Message(
        link_id=link_id,
        recipient_user_id=recipient_user_id,
        body=body,
        sender_fingerprint_hash=fingerprint_hash,
        abuse_score=filter_result.score,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    severity = filter_result.severity
    if severity == Severity.L3:
        session.add(
            ModerationAction(
                target=f"message:{message.id}",
                action="auto_flag",
                severity=Severity.L3.value,
                reason=body,  # evidence snapshot preserved before the content is hidden
            )
        )
        # Auto-remove from the recipient's view pending human review.
        message.body = ""
        message.deleted_at = datetime.now(timezone.utc)
        await session.commit()
    else:
        if severity in (Severity.L2, Severity.L1):
            session.add(
                ModerationAction(
                    target=f"message:{message.id}",
                    action="auto_flag",
                    severity=severity.value,
                )
            )
            await session.commit()
        await _enqueue_notification(redis, message.id)

    return SendResult(status=SendStatus.STORED, message_id=message.id)


async def get_inbox_messages(session: AsyncSession, recipient_user_id: int, limit: int = 20) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.recipient_user_id == recipient_user_id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_unread(session: AsyncSession, recipient_user_id: int) -> int:
    result = await session.execute(
        select(func.count(Message.id)).where(
            Message.recipient_user_id == recipient_user_id,
            Message.deleted_at.is_(None),
            Message.opened_at.is_(None),
        )
    )
    return result.scalar_one()


async def get_message_for_recipient(
    session: AsyncSession, message_id: int, recipient_user_id: int
) -> Message | None:
    result = await session.execute(
        select(Message).where(
            Message.id == message_id,
            Message.recipient_user_id == recipient_user_id,
            Message.deleted_at.is_(None),
        )
    )
    return result.scalars().first()


async def mark_opened(session: AsyncSession, message: Message) -> None:
    if message.opened_at is None:
        message.opened_at = datetime.now(timezone.utc)
        await session.commit()
