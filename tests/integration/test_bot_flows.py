"""Integration tests: bot handlers exercised as plain async functions against
the real DB session/service layer (no live Telegram connection needed)."""

from core.config import get_settings
from core.models import Block, Message, ModerationAction, PublicLink, Report, User
from core.services.links import create_link
from core.services.messages import send_message

from bot.handlers import inbox, moderation, settings as settings_handlers, start
from tests.fakes import FakeCallbackQuery, FakeMessage

settings = get_settings()


async def _seed_message(db_session, fake_redis, recipient_id: int, body: str = "Salom, qalaysan?"):
    db_session.add(User(tg_user_id=recipient_id))
    await db_session.commit()
    link = await create_link(db_session, owner_user_id=recipient_id)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=recipient_id,
        body=body, fingerprint_hash="fp-seed", acknowledge_warning=True,
    )
    return link, result.message_id


async def test_start_command_first_time_shows_language(db_session, clean_tables):
    message = FakeMessage(user_id=1001, text="/start")
    await start.cmd_start(message, db_session, settings)

    assert "Tilni tanlang" in message.sent[0]["text"]
    user = await db_session.get(User, 1001)
    assert user is not None


async def test_start_command_returning_user_skips_language(db_session, clean_tables):
    db_session.add(User(tg_user_id=1002, lang="uz"))
    await db_session.commit()

    message = FakeMessage(user_id=1002, text="/start")
    await start.cmd_start(message, db_session, settings)

    assert "Tilni tanlang" not in message.sent[0]["text"]


async def test_language_selection_then_create_link_flow(db_session, clean_tables):
    fake_msg = FakeMessage(user_id=1003)
    lang_cb = FakeCallbackQuery(user_id=1003, data="lang:uz", message=fake_msg)
    await start.on_language_selected(lang_cb, db_session)
    assert "Havola yaratish" in fake_msg.last_text or fake_msg.edited

    create_cb = FakeCallbackQuery(user_id=1003, data="link:create", message=fake_msg)
    await start.on_create_link(create_cb, db_session, settings)

    link = await db_session.execute(
        __import__("sqlalchemy").select(PublicLink).where(PublicLink.owner_user_id == 1003)
    )
    stored_link = link.scalars().first()
    assert stored_link is not None
    assert stored_link.token in fake_msg.last_text


async def test_inbox_open_empty_state(db_session, clean_tables):
    db_session.add(User(tg_user_id=1004))
    await db_session.commit()
    fake_msg = FakeMessage(user_id=1004)
    cb = FakeCallbackQuery(user_id=1004, data="inbox:open", message=fake_msg)

    await inbox.on_inbox_open(cb, db_session)

    assert "Hozircha xabar yo'q" in fake_msg.last_text


async def test_inbox_open_lists_message_and_open_marks_read(db_session, clean_tables, fake_redis):
    _, message_id = await _seed_message(db_session, fake_redis, 1005)

    fake_msg = FakeMessage(user_id=1005)
    cb = FakeCallbackQuery(user_id=1005, data="inbox:open", message=fake_msg)
    await inbox.on_inbox_open(cb, db_session)
    assert "Salom" not in fake_msg.last_text  # inbox shows previews via buttons, not inline body text

    open_cb = FakeCallbackQuery(user_id=1005, data=f"msg:open:{message_id}", message=fake_msg)
    await inbox.on_message_open(open_cb, db_session)

    stored = await db_session.get(Message, message_id)
    assert stored.opened_at is not None
    assert "Salom, qalaysan?" in fake_msg.last_text


async def test_report_flow_creates_report_and_bumps_abuse_score(db_session, clean_tables, fake_redis):
    _, message_id = await _seed_message(db_session, fake_redis, 1006)
    fake_msg = FakeMessage(user_id=1006)

    reason_cb = FakeCallbackQuery(user_id=1006, data=f"msg:reportreason:{message_id}:harassment", message=fake_msg)
    await inbox.on_report_reason(reason_cb, db_session, settings)

    from sqlalchemy import select
    result = await db_session.execute(select(Report).where(Report.message_id == message_id))
    report = result.scalars().first()
    assert report is not None
    assert report.reason == "harassment"
    assert report.body_snapshot == "Salom, qalaysan?"

    stored = await db_session.get(Message, message_id)
    assert stored.abuse_score >= 2


async def test_block_flow_prevents_future_sends(db_session, clean_tables, fake_redis):
    link, message_id = await _seed_message(db_session, fake_redis, 1007, )
    fake_msg = FakeMessage(user_id=1007)

    block_cb = FakeCallbackQuery(user_id=1007, data=f"msg:blockconfirm:{message_id}", message=fake_msg)
    await inbox.on_block_confirm(block_cb, db_session)

    from sqlalchemy import select
    result = await db_session.execute(select(Block).where(Block.user_id == 1007))
    assert result.scalars().first() is not None

    # A second send attempt from the same fingerprint is now silently dropped.
    second = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=1007,
        body="hello again", fingerprint_hash="fp-seed",
    )
    from core.services.messages import SendStatus
    assert second.status == SendStatus.BLOCKED_SILENT


async def test_delete_flow_clears_body(db_session, clean_tables, fake_redis):
    _, message_id = await _seed_message(db_session, fake_redis, 1008)
    fake_msg = FakeMessage(user_id=1008)

    delete_cb = FakeCallbackQuery(user_id=1008, data=f"msg:deleteconfirm:{message_id}", message=fake_msg)
    await inbox.on_delete_confirm(delete_cb, db_session)

    stored = await db_session.get(Message, message_id)
    assert stored.body == ""
    assert stored.deleted_at is not None


async def test_regenerate_link_flow(db_session, clean_tables):
    db_session.add(User(tg_user_id=1009))
    await db_session.commit()
    old_link = await create_link(db_session, owner_user_id=1009)

    fake_msg = FakeMessage(user_id=1009)
    cb = FakeCallbackQuery(user_id=1009, data="settings:regenerateconfirm", message=fake_msg)
    await settings_handlers.on_regenerate_confirm(cb, db_session, settings)

    await db_session.refresh(old_link)
    assert old_link.active is False
    new_text = fake_msg.edited[-1]["text"]
    assert old_link.token not in new_text


async def test_modqueue_hidden_from_non_admin(db_session, clean_tables):
    fake_msg = FakeMessage(user_id=42)  # not in ADMIN_TG_USER_IDS
    await moderation.cmd_modqueue(fake_msg, db_session, settings)
    assert fake_msg.sent == []


async def test_modqueue_visible_to_admin_and_dismiss_writes_audit_log(db_session, clean_tables, fake_redis):
    admin_id = next(iter(settings.admin_ids))
    _, message_id = await _seed_message(db_session, fake_redis, 1010, body="sen ahmoqsan")  # L2 harassment

    fake_msg = FakeMessage(user_id=admin_id)
    admin_msg = FakeMessage(user_id=admin_id)
    await moderation.cmd_modqueue(admin_msg, db_session, settings)
    assert len(admin_msg.sent) >= 1

    from sqlalchemy import select
    result = await db_session.execute(
        select(ModerationAction).where(ModerationAction.target == f"message:{message_id}")
    )
    action = result.scalars().first()
    assert action is not None

    dismiss_cb = FakeCallbackQuery(user_id=admin_id, data=f"mod:dismiss:{action.id}", message=fake_msg)
    await moderation.on_moderation_decision(dismiss_cb, db_session, settings)

    result2 = await db_session.execute(
        select(ModerationAction).where(
            ModerationAction.target == f"message:{message_id}", ModerationAction.action == "dismiss"
        )
    )
    assert result2.scalars().first() is not None
