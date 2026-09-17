"""End-to-end: the complete journey across all three surfaces —
recipient creates a link (bot) -> sender sends via the real HTTP web layer ->
notification worker delivers it -> recipient opens/reports/blocks/deletes (bot).
"""

import re

import httpx
from httpx import ASGITransport

from core.config import get_settings
from core.models import Message, User
from tests.fakes import FakeBot, FakeCallbackQuery, FakeMessage
from workers import notifier

from bot.handlers import inbox, start

settings = get_settings()


async def test_full_recipient_to_sender_to_delivery_to_action_journey(db_session, clean_tables, fake_redis):
    recipient_id = 9999001

    # 1. Recipient creates a link via the bot.
    start_msg = FakeMessage(user_id=recipient_id, text="/start")
    await start.cmd_start(start_msg, db_session, settings)

    lang_cb = FakeCallbackQuery(user_id=recipient_id, data="lang:uz", message=start_msg)
    await start.on_language_selected(lang_cb, db_session)

    create_cb = FakeCallbackQuery(user_id=recipient_id, data="link:create", message=start_msg)
    await start.on_create_link(create_cb, db_session, settings)

    link_text = start_msg.last_text
    token_match = re.search(r"/s/([a-f0-9]{32})", link_text)
    assert token_match, f"no token found in: {link_text}"
    token = token_match.group(1)

    # 2. Sender opens the real web page and sends a message (real HTTP layer).
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        page = await client.get(f"/s/{token}")
        assert page.status_code == 200
        csrf = re.search(r'const csrfToken = "([^"]+)"', page.text).group(1)

        send_resp = await client.post(
            f"/s/{token}/send",
            json={"message": "Sen ajoyibsan, davom et!", "csrf_token": csrf},
        )
    assert send_resp.json()["status"] == "success"

    from sqlalchemy import select

    result = await db_session.execute(select(Message).where(Message.recipient_user_id == recipient_id))
    message = result.scalars().first()
    assert message is not None
    assert message.notified_at is None  # not yet delivered

    # 3. Notification worker picks it up and delivers it.
    bot = FakeBot()
    delivered = await notifier.process_one(bot, db_session, fake_redis, timeout=1)
    assert delivered is True
    assert bot.sent[0]["chat_id"] == recipient_id

    await db_session.refresh(message)
    assert message.notified_at is not None

    # 4. Recipient opens the inbox, then the message (bot).
    inbox_cb = FakeCallbackQuery(user_id=recipient_id, data="inbox:open", message=start_msg)
    await inbox.on_inbox_open(inbox_cb, db_session, settings)
    assert "Sen ajoyibsan" not in start_msg.last_text  # previews only, full body on open

    open_cb = FakeCallbackQuery(user_id=recipient_id, data=f"msg:open:{message.id}", message=start_msg)
    await inbox.on_message_open(open_cb, db_session)
    assert "Sen ajoyibsan, davom et!" in start_msg.last_text

    await db_session.refresh(message)
    assert message.opened_at is not None

    # 5. Recipient reports it, then blocks the sender, then deletes it.
    report_cb = FakeCallbackQuery(
        user_id=recipient_id, data=f"msg:reportreason:{message.id}:other", message=start_msg
    )
    await inbox.on_report_reason(report_cb, db_session, settings)

    block_cb = FakeCallbackQuery(user_id=recipient_id, data=f"msg:blockconfirm:{message.id}", message=start_msg)
    await inbox.on_block_confirm(block_cb, db_session, settings)

    delete_cb = FakeCallbackQuery(user_id=recipient_id, data=f"msg:deleteconfirm:{message.id}", message=start_msg)
    await inbox.on_delete_confirm(delete_cb, db_session, settings)

    await db_session.refresh(message)
    assert message.body == ""
    assert message.deleted_at is not None

    from core.models import Block, Report

    reports = await db_session.execute(select(Report).where(Report.message_id == message.id))
    assert reports.scalars().first() is not None

    blocks = await db_session.execute(select(Block).where(Block.user_id == recipient_id))
    assert blocks.scalars().first() is not None
