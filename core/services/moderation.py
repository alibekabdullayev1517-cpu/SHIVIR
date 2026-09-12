"""Recipient-facing safety actions (report/block/delete) and the moderation
queue they feed. No separate sender-identity table exists (by design, for
anonymity) — mass-abuse detection instead correlates by `sender_fingerprint_hash`
across messages, which is the only stable signal we retain.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Block, Message, ModerationAction, PublicLink, Report, ReportStatus


async def report_message(
    session: AsyncSession, message: Message, reason: str, *, auto_disable_threshold: int
) -> Report:
    report = Report(message_id=message.id, reason=reason, body_snapshot=message.body)
    session.add(report)

    # Reporting implies protective action: bump the message's own abuse signal
    # without requiring the recipient to also tap Block separately.
    message.abuse_score += 2

    link = await session.get(PublicLink, message.link_id)
    if link is not None:
        link.report_count += 1
        if link.report_count >= auto_disable_threshold and link.active:
            link.active = False
            session.add(
                ModerationAction(
                    target=f"link:{link.id}",
                    action="disable_link",
                    severity="L2",
                    moderator="system",
                    reason="auto-disabled: report_count threshold reached",
                )
            )

    await session.commit()
    await session.refresh(report)
    return report


async def block_sender(session: AsyncSession, user_id: int, fingerprint_hash: str) -> None:
    exists = await session.execute(
        select(Block).where(Block.user_id == user_id, Block.sender_fingerprint_hash == fingerprint_hash)
    )
    if exists.scalars().first() is not None:
        return
    session.add(Block(user_id=user_id, sender_fingerprint_hash=fingerprint_hash))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()


async def delete_message(session: AsyncSession, message: Message) -> None:
    """A real delete: the content is gone. Evidence for any open report survives
    only in that report's own `body_snapshot`, captured at report time."""
    message.body = ""
    message.deleted_at = datetime.now(timezone.utc)
    await session.commit()


async def sender_report_count(session: AsyncSession, fingerprint_hash: str) -> int:
    """How many reports exist against messages from this fingerprint, across all
    links/recipients — the mass-abuse signal."""
    result = await session.execute(
        select(func.count(Report.id))
        .join(Message, Report.message_id == Message.id)
        .where(Message.sender_fingerprint_hash == fingerprint_hash)
    )
    return result.scalar_one()


async def _resolve_link_for_target(session: AsyncSession, target: str) -> PublicLink | None:
    kind, _, raw_id = target.partition(":")
    if not raw_id.isdigit():
        return None
    if kind == "link":
        return await session.get(PublicLink, int(raw_id))
    if kind == "message":
        message = await session.get(Message, int(raw_id))
        if message is not None:
            return await session.get(PublicLink, message.link_id)
    return None


async def apply_moderator_decision(
    session: AsyncSession, moderator_id: int, action_id: int, decision: str
) -> ModerationAction | None:
    """Every moderator action is a new append-only audit-log row, per spec, never
    a mutation of the original auto-flag entry."""
    original = await session.get(ModerationAction, action_id)
    if original is None:
        return None

    entry = ModerationAction(
        target=original.target,
        action=decision,
        severity=original.severity,
        moderator=str(moderator_id),
    )
    session.add(entry)

    if decision == "disable_link":
        link = await _resolve_link_for_target(session, original.target)
        if link is not None:
            link.active = False

    await session.commit()
    await session.refresh(entry)
    return entry


async def moderation_queue(session: AsyncSession, limit: int = 50) -> list[ModerationAction]:
    """Severity-then-recency queue for human moderators (bot-command based in V1;
    no separate admin dashboard yet — that's V2+)."""
    severity_order = {"L3": 0, "L2": 1, "L1": 2}
    result = await session.execute(
        select(ModerationAction).order_by(ModerationAction.created_at.desc()).limit(limit * 3)
    )
    actions = list(result.scalars().all())
    actions.sort(key=lambda a: (severity_order.get(a.severity, 3), -a.created_at.timestamp()))
    return actions[:limit]
