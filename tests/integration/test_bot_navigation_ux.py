"""Regression tests for the 3 bot UX fixes: persistent main-action
ReplyKeyboardMarkup, "back" navigation in submenus, and a working native
Telegram share flow for "Ulashish"."""

from urllib.parse import parse_qs, urlparse

from aiogram.types import ReplyKeyboardMarkup

from core.config import get_settings
from core.models import PublicLink, User
from core.services.links import build_sender_url

from bot.handlers import inbox, settings as settings_handlers, start
from bot.keyboards import link_ready_keyboard, report_reason_keyboard
from tests.fakes import FakeCallbackQuery, FakeMessage

settings = get_settings()


def _inline_button(markup, callback_data=None, url_prefix=None):
    for row in markup.inline_keyboard:
        for btn in row:
            if callback_data is not None and btn.callback_data == callback_data:
                return btn
            if url_prefix is not None and btn.url and btn.url.startswith(url_prefix):
                return btn
    return None


# --- 1. Persistent main-action keyboard -------------------------------------


async def test_returning_user_start_gets_persistent_reply_keyboard(db_session, clean_tables):
    db_session.add(User(tg_user_id=3001, lang="uz"))
    await db_session.commit()

    message = FakeMessage(user_id=3001, text="/start")
    await start.cmd_start(message, db_session, settings)

    markup = message.sent[-1]["reply_markup"]
    assert isinstance(markup, ReplyKeyboardMarkup)
    labels = {btn.text for row in markup.keyboard for btn in row}
    assert labels == {"📥 Qutim", "🔗 Havolam", "⚙️ Sozlamalar"}


async def test_new_user_first_link_creation_attaches_persistent_keyboard(db_session, clean_tables):
    fake_msg = FakeMessage(user_id=3002)
    lang_cb = FakeCallbackQuery(user_id=3002, data="lang:uz", message=fake_msg)
    await start.on_language_selected(lang_cb, db_session)

    create_cb = FakeCallbackQuery(user_id=3002, data="link:create", message=fake_msg)
    await start.on_create_link(create_cb, db_session, settings)

    # The link-ready screen itself is an edit (can't carry a reply keyboard);
    # the keyboard must arrive via a separate, real new message.
    assert len(fake_msg.sent) == 1
    markup = fake_msg.sent[-1]["reply_markup"]
    assert isinstance(markup, ReplyKeyboardMarkup)


async def test_existing_user_recreating_link_does_not_resend_keyboard(db_session, clean_tables):
    """Avoid duplicate keyboards: the follow-up message is only for a
    genuinely first-ever link, not every time link:create fires (e.g. the
    message-detail screen's "Havola yaratish" button for an existing user)."""
    db_session.add(User(tg_user_id=3003, lang="uz"))
    await db_session.commit()

    from core.services.links import create_link as _create_link

    await _create_link(db_session, owner_user_id=3003)

    fake_msg = FakeMessage(user_id=3003)
    create_cb = FakeCallbackQuery(user_id=3003, data="link:create", message=fake_msg)
    await start.on_create_link(create_cb, db_session, settings)

    assert fake_msg.sent == []  # no extra "main menu ready" message


# --- 2. Back navigation -------------------------------------------------------


def test_report_reason_keyboard_has_back_button_to_message_detail():
    markup = report_reason_keyboard(message_id=555, lang="uz")
    back = _inline_button(markup, callback_data="msg:open:555")
    assert back is not None
    assert back.text == "◀️ Orqaga"


async def test_settings_back_buttons_use_orqaga_label(db_session, clean_tables):
    db_session.add(User(tg_user_id=3004, lang="uz"))
    await db_session.commit()

    fake_msg = FakeMessage(user_id=3004)
    open_cb = FakeCallbackQuery(user_id=3004, data="settings:open", message=fake_msg)
    await settings_handlers.on_settings_open(open_cb, db_session)
    markup = fake_msg.edited[-1]["reply_markup"]
    back = _inline_button(markup, callback_data="home:open")
    assert back is not None and back.text == "◀️ Orqaga"

    safety_cb = FakeCallbackQuery(user_id=3004, data="settings:safety", message=fake_msg)
    await settings_handlers.on_safety(safety_cb, db_session)
    markup = fake_msg.edited[-1]["reply_markup"]
    back = _inline_button(markup, callback_data="settings:open")
    assert back is not None and back.text == "◀️ Orqaga"


async def test_home_open_returns_to_home_without_duplicating_inline_keyboard(db_session, clean_tables):
    """"◀️ Orqaga" from Settings must return to the actual previous state
    (Home), not reset via /start, and must not leave a stale inline keyboard
    now that the 3 main actions live on the persistent reply keyboard."""
    db_session.add(User(tg_user_id=3005, lang="uz"))
    await db_session.commit()

    fake_msg = FakeMessage(user_id=3005)
    cb = FakeCallbackQuery(user_id=3005, data="home:open", message=fake_msg)
    await start.on_home_open(cb, db_session)

    assert fake_msg.edited[-1]["text"] == "Bosh sahifa"
    assert fake_msg.edited[-1]["reply_markup"] is None


# --- 3. Real Telegram share flow ----------------------------------------------


async def test_ulashish_button_is_real_telegram_share_url_with_actual_link(db_session, clean_tables):
    db_session.add(User(tg_user_id=3006, lang="uz"))
    await db_session.commit()

    fake_msg = FakeMessage(user_id=3006)
    create_cb = FakeCallbackQuery(user_id=3006, data="link:create", message=fake_msg)
    await start.on_create_link(create_cb, db_session, settings)

    markup = fake_msg.edited[-1]["reply_markup"]
    share_btn = _inline_button(markup, url_prefix="https://t.me/share/url?")
    assert share_btn is not None

    parsed = urlparse(share_btn.url)
    assert parsed.netloc == "t.me"
    assert parsed.path == "/share/url"
    query = parse_qs(parsed.query)

    from sqlalchemy import select

    result = await db_session.execute(select(PublicLink).where(PublicLink.owner_user_id == 3006))
    link = result.scalars().first()
    real_url = build_sender_url(settings.web_base_url, link.token)

    assert query["url"] == [real_url]
    assert "share_message" not in query  # sanity: only url/text params exist
    assert query["text"]  # a real, non-empty share message is present


def test_link_ready_keyboard_never_fabricates_a_different_domain():
    markup = link_ready_keyboard("uz", "https://shivir.online/s/realtoken123")
    share_btn = _inline_button(markup, url_prefix="https://t.me/share/url?")
    parsed_query = parse_qs(urlparse(share_btn.url).query)
    assert parsed_query["url"] == ["https://shivir.online/s/realtoken123"]


async def test_copy_link_fallback_tracks_analytics_and_shows_toast(db_session, clean_tables):
    db_session.add(User(tg_user_id=3007, lang="uz"))
    await db_session.commit()
    from core.services.links import create_link as _create_link

    await _create_link(db_session, owner_user_id=3007)

    fake_msg = FakeMessage(user_id=3007)
    copy_cb = FakeCallbackQuery(user_id=3007, data="link:copy", message=fake_msg)
    await start.on_link_copy(copy_cb, db_session)

    assert copy_cb.answers[-1]["show_alert"] is True
    assert copy_cb.answers[-1]["text"]

    from sqlalchemy import select

    from core.models import Event

    result = await db_session.execute(select(Event).where(Event.name == "link_shared"))
    event = result.scalars().first()
    assert event is not None
    assert event.props["channel"] == "copy"


# --- Tapping the 3 persistent reply-keyboard buttons directly --------------


async def test_reply_keyboard_inbox_button_opens_inbox(db_session, clean_tables):
    db_session.add(User(tg_user_id=3009, lang="uz"))
    await db_session.commit()

    message = FakeMessage(user_id=3009, text="📥 Qutim")
    await inbox.on_inbox_open_reply_button(message, db_session, settings)

    assert "Hozircha xabar yo'q" in message.sent[-1]["text"]


async def test_reply_keyboard_my_link_button_shows_real_link(db_session, clean_tables):
    db_session.add(User(tg_user_id=3010, lang="uz"))
    await db_session.commit()

    message = FakeMessage(user_id=3010, text="🔗 Havolam")
    await start.on_link_show_reply_button(message, db_session, settings)

    from sqlalchemy import select

    result = await db_session.execute(select(PublicLink).where(PublicLink.owner_user_id == 3010))
    link = result.scalars().first()
    assert link is not None
    assert link.token in message.sent[-1]["text"]


async def test_reply_keyboard_settings_button_opens_settings(db_session, clean_tables):
    db_session.add(User(tg_user_id=3011, lang="uz"))
    await db_session.commit()

    message = FakeMessage(user_id=3011, text="⚙️ Sozlamalar")
    await settings_handlers.on_settings_open_reply_button(message, db_session)

    assert "Sozlamalar" in message.sent[-1]["text"]


async def test_reply_keyboard_buttons_work_in_russian_too(db_session, clean_tables):
    db_session.add(User(tg_user_id=3012, lang="ru"))
    await db_session.commit()

    inbox_msg = FakeMessage(user_id=3012, text="📥 Входящие")
    await inbox.on_inbox_open_reply_button(inbox_msg, db_session, settings)
    assert inbox_msg.sent

    settings_msg = FakeMessage(user_id=3012, text="⚙️ Настройки")
    await settings_handlers.on_settings_open_reply_button(settings_msg, db_session)
    assert "Настройки" in settings_msg.sent[-1]["text"]


async def test_no_automatic_message_sent_by_share_flow(db_session, clean_tables):
    """Tapping Ulashish/copy must never itself deliver a message anywhere —
    only the user's own choice inside Telegram's native share UI does."""
    db_session.add(User(tg_user_id=3008, lang="uz"))
    await db_session.commit()
    from core.services.links import create_link as _create_link

    await _create_link(db_session, owner_user_id=3008)

    fake_msg = FakeMessage(user_id=3008)
    copy_cb = FakeCallbackQuery(user_id=3008, data="link:copy", message=fake_msg)
    await start.on_link_copy(copy_cb, db_session)

    # on_link_copy only ever answers the callback (a toast) — it must never
    # send or edit a message.
    assert fake_msg.sent == []
    assert fake_msg.edited == []
