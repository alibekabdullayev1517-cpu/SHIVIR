"""'🖼 Karta sifatida' — the Telegram callback behind the share card."""

import io

from PIL import Image
from sqlalchemy import update

from core.config import get_settings
from core.copy import t
from core.models import Message, User
from core.services.links import create_link
from core.services.messages import send_message

from bot.handlers import inbox
from tests.fakes import FakeCallbackQuery, FakeMessage

settings = get_settings()


async def _seed(db_session, fake_redis, recipient_id: int, body: str = "Sen haqingda juda yaxshi fikrdaman!", lang: str = "uz"):
    db_session.add(User(tg_user_id=recipient_id, lang=lang))
    await db_session.commit()
    link = await create_link(db_session, owner_user_id=recipient_id)
    result = await send_message(
        db_session, fake_redis, settings,
        link_id=link.id, link_active=link.active, recipient_user_id=recipient_id,
        body=body, fingerprint_hash="fp-card", acknowledge_warning=True,
    )
    return result.message_id


def _cb(user_id: int, data: str):
    msg = FakeMessage(user_id=user_id)
    return FakeCallbackQuery(user_id=user_id, data=data, message=msg), msg


async def test_card_is_generated_and_sent_as_1080_png_without_caption(db_session, fake_redis, clean_tables):
    message_id = await _seed(db_session, fake_redis, 7101)
    cb, msg = _cb(7101, f"msg:card:{message_id}")

    await inbox.on_share_card(cb, db_session, settings)

    assert len(msg.photos) == 1
    photo = msg.photos[0]
    assert photo["caption"] is None  # the message is in the image; nothing else is sent with it
    image = Image.open(io.BytesIO(photo["photo"].data))
    assert image.format == "PNG" and image.size == (1080, 1080)
    assert msg.sent == []  # no error message
    assert cb.answers == [{"text": None, "show_alert": False}]  # spinner ended, exactly once


async def test_callback_is_acknowledged_before_the_card_is_rendered(db_session, fake_redis, clean_tables, monkeypatch):
    message_id = await _seed(db_session, fake_redis, 7102)
    cb, msg = _cb(7102, f"msg:card:{message_id}")
    seen = {}

    def spy(body):
        seen["answered_before_render"] = len(cb.answers) == 1
        seen["body"] = body
        return inbox_render(body)

    from cards.render import render_share_card as inbox_render
    monkeypatch.setattr(inbox, "render_share_card", spy)

    await inbox.on_share_card(cb, db_session, settings)

    assert seen == {"answered_before_render": True, "body": "Sen haqingda juda yaxshi fikrdaman!"}


async def test_exact_message_body_is_what_gets_rendered(db_session, fake_redis, clean_tables, monkeypatch):
    body = "Aynan shu matn 🔥 — «o‘zgarmasdan»!"
    message_id = await _seed(db_session, fake_redis, 7103, body=body)
    cb, msg = _cb(7103, f"msg:card:{message_id}")
    received = []
    monkeypatch.setattr(inbox, "render_share_card", lambda b: received.append(b) or b"\x89PNG-fake")

    await inbox.on_share_card(cb, db_session, settings)

    assert received == [body]


async def test_200_character_message_works(db_session, fake_redis, clean_tables):
    message_id = await _seed(db_session, fake_redis, 7104, body="x" * 3 + " so'z" * 39)
    cb, msg = _cb(7104, f"msg:card:{message_id}")
    await inbox.on_share_card(cb, db_session, settings)
    assert len(msg.photos) == 1


async def test_someone_elses_message_is_refused(db_session, fake_redis, clean_tables, monkeypatch):
    message_id = await _seed(db_session, fake_redis, 7105)
    db_session.add(User(tg_user_id=7106, lang="uz"))
    await db_session.commit()
    monkeypatch.setattr(inbox, "render_share_card", lambda b: (_ for _ in ()).throw(AssertionError("must not render")))
    cb, msg = _cb(7106, f"msg:card:{message_id}")  # 7106 is not the recipient

    await inbox.on_share_card(cb, db_session, settings)

    assert msg.photos == [] and msg.sent == []
    assert cb.answers == [{"text": t("generic_error", "uz"), "show_alert": True}]


async def test_missing_message_is_refused(db_session, clean_tables):
    db_session.add(User(tg_user_id=7107, lang="uz"))
    await db_session.commit()
    cb, msg = _cb(7107, "msg:card:999999")

    await inbox.on_share_card(cb, db_session, settings)

    assert msg.photos == []
    assert cb.answers == [{"text": t("generic_error", "uz"), "show_alert": True}]


async def test_deleted_message_is_refused(db_session, fake_redis, clean_tables):
    from datetime import datetime, timezone

    message_id = await _seed(db_session, fake_redis, 7108)
    await db_session.execute(update(Message).where(Message.id == message_id).values(deleted_at=datetime.now(timezone.utc)))
    await db_session.commit()
    cb, msg = _cb(7108, f"msg:card:{message_id}")

    await inbox.on_share_card(cb, db_session, settings)

    assert msg.photos == []
    assert cb.answers[0]["show_alert"] is True


async def test_malformed_callback_data_does_not_crash(db_session, clean_tables):
    db_session.add(User(tg_user_id=7109, lang="ru"))
    await db_session.commit()
    for data in ("msg:card:", "msg:card:abc", "msg:card:1.5", "msg:card"):
        cb, msg = _cb(7109, data)
        await inbox.on_share_card(cb, db_session, settings)
        assert msg.photos == []
        assert cb.answers == [{"text": t("generic_error", "ru"), "show_alert": True}]


async def test_render_failure_shows_clean_error_and_leaks_nothing(db_session, fake_redis, clean_tables, monkeypatch, caplog):
    body = "Maxfiy xabar matni"
    message_id = await _seed(db_session, fake_redis, 7110, body=body, lang="ru")

    def boom(_body):
        raise RuntimeError("/opt/shivir/cards/render.py: secret internal failure")

    monkeypatch.setattr(inbox, "render_share_card", boom)
    cb, msg = _cb(7110, f"msg:card:{message_id}")

    await inbox.on_share_card(cb, db_session, settings)

    assert msg.photos == []
    assert [m["text"] for m in msg.sent] == [t("generic_error", "ru")]  # plain-language copy only
    shown = msg.sent[0]["text"]
    assert "Traceback" not in shown and "/opt/" not in shown and "render.py" not in shown
    assert body not in caplog.text  # the private message text is never written to logs
    assert len(cb.answers) == 1  # already acknowledged before the failure
