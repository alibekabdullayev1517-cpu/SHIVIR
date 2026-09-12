from sqlalchemy import select

from core.config import get_settings
from core.models import Block, Message, ModerationAction, PublicLink, User
from core.services.links import create_link, get_or_create_user
from core.services.messages import send_message
from core.services.moderation import (
    apply_moderator_decision,
    block_sender,
    delete_message,
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
