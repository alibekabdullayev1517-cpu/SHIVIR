from sqlalchemy import select

from core.config import get_settings
from core.models import Block, Message, ModerationAction, PublicLink, User
from core.services.links import create_link, get_or_create_user
from core.services.messages import send_message
from core.services.moderation import (
    apply_moderator_decision,
    block_sender,
    delete_message,
    moderation_queue,
    report_message,
    sender_report_count,
)

settings = get_settings()


async def _seed(db_session, fake_redis, recipient_id: int, fingerprint: str = "fp"):
    await get_or_create_user(db_session, recipient_id)
    link = await create_link(db_session, owner_user_id=recipient_id)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=recipient_id,
        body="hello there", fingerprint_hash=fingerprint,
    )
    message = await db_session.get(Message, result.message_id)
    return link, message


async def test_link_auto_disables_after_report_threshold(db_session, clean_tables, fake_redis):
    link, message = await _seed(db_session, fake_redis, 5001)
    for i in range(5):
        _, message = await _seed(db_session, fake_redis, 5001, fingerprint=f"fp-{i}")
        await report_message(db_session, message, "spam", auto_disable_threshold=5)

    await db_session.refresh(link)
    assert link.active is False


async def test_mass_abuse_escalation_fires_once_across_recipients(db_session, clean_tables, fake_redis):
    fingerprint = "fp-mass-abuser"
    for recipient_id in (5010, 5011, 5012):
        _, message = await _seed(db_session, fake_redis, recipient_id, fingerprint=fingerprint)
        await report_message(db_session, message, "harassment", auto_disable_threshold=999)

    count = await sender_report_count(db_session, fingerprint)
    assert count == 3

    result = await db_session.execute(
        select(ModerationAction).where(ModerationAction.target == f"fingerprint:{fingerprint}")
    )
    escalations = result.scalars().all()
    assert len(escalations) == 1  # not duplicated on the 3rd report alone
    assert escalations[0].severity == "L3"


async def test_block_sender_is_idempotent(db_session, clean_tables):
    db_session.add(User(tg_user_id=5020))
    await db_session.commit()

    await block_sender(db_session, 5020, "fp-repeat")
    await block_sender(db_session, 5020, "fp-repeat")  # should not raise / duplicate

    result = await db_session.execute(select(Block).where(Block.user_id == 5020))
    assert len(result.scalars().all()) == 1


async def test_delete_message_clears_body_but_keeps_row(db_session, clean_tables, fake_redis):
    _, message = await _seed(db_session, fake_redis, 5030)
    await delete_message(db_session, message)

    reloaded = await db_session.get(Message, message.id)
    assert reloaded is not None
    assert reloaded.body == ""
    assert reloaded.deleted_at is not None


async def test_apply_moderator_decision_disable_link_resolves_via_message_target(db_session, clean_tables, fake_redis):
    link, message = await _seed(db_session, fake_redis, 5040)
    action = ModerationAction(target=f"message:{message.id}", action="auto_flag", severity="L3")
    db_session.add(action)
    await db_session.commit()
    await db_session.refresh(action)

    result = await apply_moderator_decision(db_session, moderator_id=999999999, action_id=action.id, decision="disable_link")

    assert result is not None
    assert result.action == "disable_link"
    await db_session.refresh(link)
    assert link.active is False


async def test_apply_moderator_decision_unknown_action_id_returns_none(db_session, clean_tables):
    result = await apply_moderator_decision(db_session, moderator_id=1, action_id=999999, decision="dismiss")
    assert result is None


# --- P1: moderation_queue() resolution bug ---
#
# Root cause: apply_moderator_decision() always appended a new audit-log row
# (correct — decisions are append-only) but moderation_queue() selected every
# ModerationAction row unconditionally, with no notion of "already handled".
# So the original auto-flag entry (and even the moderator's own decision row)
# kept reappearing in /modqueue forever. Fixed by deriving resolved/open
# state from existing data: a target is resolved once any row with
# moderator != "system" exists for it — no schema change needed.


async def test_moderation_queue_shows_open_item(db_session, clean_tables):
    action = ModerationAction(target="message:1001", action="auto_flag", severity="L2")
    db_session.add(action)
    await db_session.commit()

    queue = await moderation_queue(db_session)

    assert any(item.target == "message:1001" for item in queue)


async def test_moderator_decision_resolves_item_and_it_disappears_from_queue(db_session, clean_tables):
    action = ModerationAction(target="message:2001", action="auto_flag", severity="L2")
    db_session.add(action)
    await db_session.commit()
    await db_session.refresh(action)

    before = await moderation_queue(db_session)
    assert any(item.target == "message:2001" for item in before)

    await apply_moderator_decision(db_session, moderator_id=555, action_id=action.id, decision="dismiss")

    after = await moderation_queue(db_session)
    assert not any(item.target == "message:2001" for item in after)


async def test_another_unresolved_item_remains_after_one_is_resolved(db_session, clean_tables):
    resolved_action = ModerationAction(target="message:3001", action="auto_flag", severity="L2")
    still_open_action = ModerationAction(target="message:3002", action="auto_flag", severity="L2")
    db_session.add_all([resolved_action, still_open_action])
    await db_session.commit()
    await db_session.refresh(resolved_action)
    await db_session.refresh(still_open_action)

    await apply_moderator_decision(db_session, moderator_id=555, action_id=resolved_action.id, decision="dismiss")

    queue = await moderation_queue(db_session)
    targets = {item.target for item in queue}
    assert "message:3001" not in targets
    assert "message:3002" in targets


async def test_moderation_queue_orders_by_severity_then_recency(db_session, clean_tables):
    import asyncio as _asyncio

    l1 = ModerationAction(target="message:4001", action="auto_flag", severity="L1")
    db_session.add(l1)
    await db_session.commit()
    await _asyncio.sleep(0.01)

    l3 = ModerationAction(target="message:4002", action="auto_flag", severity="L3")
    db_session.add(l3)
    await db_session.commit()
    await _asyncio.sleep(0.01)

    l2 = ModerationAction(target="message:4003", action="auto_flag", severity="L2")
    db_session.add(l2)
    await db_session.commit()

    queue = await moderation_queue(db_session)
    ours = [item for item in queue if item.target in ("message:4001", "message:4002", "message:4003")]
    assert [item.severity for item in ours] == ["L3", "L2", "L1"]


async def test_repeated_identical_moderator_decision_does_not_duplicate(db_session, clean_tables):
    action = ModerationAction(target="message:5001", action="auto_flag", severity="L2")
    db_session.add(action)
    await db_session.commit()
    await db_session.refresh(action)

    first = await apply_moderator_decision(db_session, moderator_id=555, action_id=action.id, decision="dismiss")
    second = await apply_moderator_decision(db_session, moderator_id=555, action_id=action.id, decision="dismiss")

    assert first.id == second.id  # same row returned, not a new one

    result = await db_session.execute(
        select(ModerationAction).where(ModerationAction.target == "message:5001", ModerationAction.moderator != "system")
    )
    assert len(result.scalars().all()) == 1


async def test_second_moderator_racing_a_resolved_target_gets_the_first_decision(db_session, clean_tables):
    action = ModerationAction(target="message:6001", action="auto_flag", severity="L2")
    db_session.add(action)
    await db_session.commit()
    await db_session.refresh(action)

    first = await apply_moderator_decision(db_session, moderator_id=111, action_id=action.id, decision="dismiss")
    second = await apply_moderator_decision(db_session, moderator_id=222, action_id=action.id, decision="escalate")

    assert second.id == first.id
    assert second.moderator == "111"  # whichever moderator actually resolved it first
    assert second.action == "dismiss"

    result = await db_session.execute(
        select(ModerationAction).where(ModerationAction.target == "message:6001", ModerationAction.moderator != "system")
    )
    assert len(result.scalars().all()) == 1  # the second (222) attempt did not add a row


async def test_moderation_queue_does_not_hide_unresolved_severe_reports(db_session, clean_tables):
    """An L3 item with no decision yet must never be filtered out — only
    genuinely resolved targets are excluded."""
    l3 = ModerationAction(target="message:7001", action="auto_flag", severity="L3")
    db_session.add(l3)
    await db_session.commit()

    queue = await moderation_queue(db_session)
    assert any(item.target == "message:7001" and item.severity == "L3" for item in queue)
