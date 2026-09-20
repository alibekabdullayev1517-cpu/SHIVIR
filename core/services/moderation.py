"""Recipient-facing safety actions (report/block/delete) and the moderation
queue they feed. No separate sender-identity table exists (by design, for
anonymity) — mass-abuse detection instead correlates by `sender_fingerprint_hash`
across messages, which is the only stable signal we retain.
"""

from datetime import datetime, timezone

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Block, Message, ModerationAction, PublicLink, Report, ReportStatus


MASS_ABUSE_REPORT_THRESHOLD = 3

# How urgent a recipient's report is, by the reason they picked. Only orders the
# moderator's queue — a report never removes the message or blocks anyone by itself.
REPORT_SEVERITY = {"threat": "L3", "sexual": "L3", "harassment": "L2", "spam": "L1", "other": "L1"}


async def is_already_reported(session: AsyncSession, message_id: int) -> bool:
    """Whether this message already has a report (repeat reports are no-ops)."""
    result = await session.execute(select(Report.id).where(Report.message_id == message_id).limit(1))
    return result.scalars().first() is not None


async def report_message(
    session: AsyncSession, message: Message, reason: str, *, auto_disable_threshold: int
) -> Report:
    if reason not in REPORT_SEVERITY:
        # The bot handler validates the callback value too; this keeps the
        # service safe for any other caller (and away from the String(32) column).
        raise ValueError("unknown report reason")

    # One report per message: the first counts, repeats are no-ops. Otherwise one
    # recipient could re-report the same message to inflate its abuse score, push
    # their own link to the auto-disable threshold, or fake the "mass-abuse across
    # messages" escalation against a sender.
    prior = await session.execute(select(Report).where(Report.message_id == message.id).limit(1))
    existing = prior.scalars().first()
    if existing is not None:
        return existing

    report = Report(message_id=message.id, reason=reason, body_snapshot=message.body)
    session.add(report)

    # Put the report in front of the moderator. /modqueue reads moderation_actions,
    # not reports, so without this row a single report was invisible to admins.
    # Append-only (INSERT), as the production DB role allows nothing more on this
    # table; one open item per message however many times it is reported. Carries
    # the message text the recipient reported — never the sender fingerprint/IP.
    target = f"message:{message.id}"
    already_queued = await session.execute(
        select(ModerationAction.id)
        .where(ModerationAction.target == target, ModerationAction.action == "user_report")
        .limit(1)
    )
    if already_queued.scalars().first() is None:
        session.add(
            ModerationAction(
                target=target,
                action="user_report",
                severity=REPORT_SEVERITY[reason],
                moderator="system",
                reason=f"[reported: {reason}] {message.body}",
            )
        )

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

    # Mass-abuse handling: a sender reported across multiple recipients/links is
    # a stronger signal than any single report, even if no one link crosses its
    # own auto-disable threshold. There is no cross-recipient block (blocks are
    # deliberately per-recipient), so the response is human escalation, not an
    # automatic platform-wide ban.
    total_reports = await sender_report_count(session, message.sender_fingerprint_hash)
    if total_reports >= MASS_ABUSE_REPORT_THRESHOLD:
        already_escalated = await session.execute(
            select(ModerationAction).where(
                ModerationAction.target == f"fingerprint:{message.sender_fingerprint_hash}"
            )
        )
        if already_escalated.scalars().first() is None:
            session.add(
                ModerationAction(
                    target=f"fingerprint:{message.sender_fingerprint_hash}",
                    action="escalate",
                    severity="L3",
                    moderator="system",
                    reason=f"mass-abuse signal: {total_reports} reports across messages from this sender",
                )
            )
            await session.commit()

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


async def _existing_human_decision(session: AsyncSession, target: str) -> ModerationAction | None:
    """The first human (non-"system") decision recorded against this target,
    if any — that's what makes a target "resolved". Auto-generated rows
    (auto_flag, the link auto-disable, the mass-abuse escalation) all use
    moderator="system" and never count as a resolution on their own; a human
    remains the final authority on anything above L1, per the master plan."""
    result = await session.execute(
        select(ModerationAction)
        .where(ModerationAction.target == target, ModerationAction.moderator != "system")
        .order_by(ModerationAction.created_at.asc())
        .limit(1)
    )
    return result.scalars().first()


async def apply_moderator_decision(
    session: AsyncSession, moderator_id: int, action_id: int, decision: str
) -> ModerationAction | None:
    """Every moderator action is a new append-only audit-log row, per spec, never
    a mutation of the original auto-flag entry.

    Idempotent: if this target already has a human decision (a moderator
    double-tapping the same button, or two moderators racing on the same
    item), that existing decision is returned as-is rather than appending a
    duplicate — the target was already resolved by whichever came first.
    """
    original = await session.get(ModerationAction, action_id)
    if original is None:
        return None

    existing = await _existing_human_decision(session, original.target)
    if existing is not None:
        return existing

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
    """Severity-then-recency queue of items with no human decision yet.

    Resolved/open state is derived from existing data, not a separate
    stored flag: a target is "resolved" the moment any row with
    moderator != "system" exists for it (see _existing_human_decision).
    Human decisions are themselves append-only audit rows and are never
    surfaced back into the queue as if they were new items needing review.
    """
    resolved_targets = (
        select(ModerationAction.target).where(ModerationAction.moderator != "system").distinct()
    )

    # Severity is ordered in SQL (not after a size-limited fetch), so a backlog of
    # low-severity items can never push an older L3 out of the result.
    severity_rank = case(
        (ModerationAction.severity == "L3", 0),
        (ModerationAction.severity == "L2", 1),
        (ModerationAction.severity == "L1", 2),
        else_=3,
    )
    result = await session.execute(
        select(ModerationAction)
        .where(ModerationAction.moderator == "system", ModerationAction.target.notin_(resolved_targets))
        .order_by(severity_rank, ModerationAction.created_at.desc(), ModerationAction.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
