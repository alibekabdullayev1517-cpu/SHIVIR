"""V1 upgrade: pause link, owner-chosen link line (presets), sender success invite,
integrity/anonymity wording. Web routes and bot handlers exercised end to end."""

import html as htmllib
import re

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select

from core.config import get_settings
from core.copy import COPY, t
from core.link_prompts import DEFAULT_KEY, PRESET_KEYS, PRESETS, label_for, line_for
from core.models import Event, Message, PublicLink, User
from core.services.links import create_link, get_prompt_key, is_paused

from bot.handlers import settings as settings_handlers
from bot.handlers import start as start_handlers
from bot.keyboards import prompt_keyboard, settings_keyboard
from tests.fakes import FakeCallbackQuery, FakeMessage

settings = get_settings()


@pytest_asyncio.fixture
async def client(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


async def _owner(db_session, tg_id: int, lang: str = "uz", **extra_settings):
    db_session.add(User(tg_user_id=tg_id, lang=lang, settings={"display_name": "Ali Valiyev", **extra_settings}))
    await db_session.commit()
    return await create_link(db_session, owner_user_id=tg_id)


def _csrf(html: str) -> str:
    match = re.search(r'const csrfToken = "([^"]+)"', html)
    assert match
    return match.group(1)


async def _events(db_session, name: str):
    result = await db_session.execute(select(Event).where(Event.name == name))
    return result.scalars().all()


async def _reload(db_session, tg_id: int) -> User:
    await db_session.rollback()
    db_session.expire_all()
    return await db_session.get(User, tg_id)


# --------------------------------------------------------------------------
# Owner-chosen line on the sender page (presets only)
# --------------------------------------------------------------------------

async def test_default_page_shows_the_standard_hint(client, db_session, clean_tables):
    link = await _owner(db_session, 8001)
    html = (await client.get(f"/s/{link.token}")).text
    assert t("sender_hint", "uz") in html


async def test_preset_line_is_shown_to_senders_in_the_owners_language(client, db_session, clean_tables):
    link_uz = await _owner(db_session, 8002, "uz", prompt="birthday")
    link_ru = await _owner(db_session, 8003, "ru", prompt="honest")
    uz = (await client.get(f"/s/{link_uz.token}")).text
    ru = (await client.get(f"/s/{link_ru.token}")).text
    assert line_for("birthday", "uz") in htmllib.unescape(uz) and t("sender_hint", "uz") not in uz
    assert line_for("honest", "ru") in htmllib.unescape(ru)


async def test_tampered_or_stale_prompt_value_is_never_rendered(client, db_session, clean_tables):
    """Even if settings["prompt"] were corrupted directly in the DB, only an
    allow-listed preset can ever reach the page — no free text, no markup."""
    for tg_id, evil in ((8004, "<script>alert(1)</script>"), (8005, "birthdayX"), (8006, {"a": 1}), (8007, 5)):
        link = await _owner(db_session, tg_id, "uz", prompt=evil)
        html = (await client.get(f"/s/{link.token}")).text
        assert "<script>alert(1)" not in html
        assert "birthdayX" not in html
        assert t("sender_hint", "uz") in html  # falls back to the default line


def test_presets_are_short_plain_and_fully_localized():
    assert set(PRESETS) == set(PRESET_KEYS) and len(PRESET_KEYS) == 7
    for key in PRESET_KEYS:
        for lang in ("uz", "ru"):
            line, label = line_for(key, lang), label_for(key, lang)
            assert line and label
            assert len(line) <= 60 and len(label) <= 24
            assert not any(ch in line + label for ch in "<>&\"`{}\\")
            assert "http" not in line.lower()
    assert line_for("nope", "uz") is None and line_for(None, "uz") is None and line_for(["x"], "uz") is None


# --------------------------------------------------------------------------
# Pause link — sender side
# --------------------------------------------------------------------------

async def test_paused_link_shows_neutral_page_without_compose_form(client, db_session, clean_tables):
    link = await _owner(db_session, 8010, "uz", paused=True)
    resp = await client.get(f"/s/{link.token}")
    assert resp.status_code == 200
    assert t("sender_paused", "uz") in resp.text
    assert 'id="composer"' not in resp.text and "csrfToken" not in resp.text
    # neutral: doesn't claim the link is broken, deleted or that anyone blocked the sender
    assert t("link_invalid", "uz") not in resp.text


async def test_paused_page_is_localized_and_unpaused_owners_are_unaffected(client, db_session, clean_tables):
    ru = await _owner(db_session, 8011, "ru", paused=True)
    live = await _owner(db_session, 8012, "uz")
    assert t("sender_paused", "ru") in (await client.get(f"/s/{ru.token}")).text
    assert 'id="composer"' in (await client.get(f"/s/{live.token}")).text


async def test_send_is_refused_while_paused_and_nothing_is_stored_or_counted(client, db_session, clean_tables):
    """A page opened BEFORE the pause can still POST. It must be refused server-side,
    store nothing, and not consume the sender's rate-limit budget."""
    link = await _owner(db_session, 8013)
    token = link.token  # captured now: the session is expired by _reload() below
    csrf = _csrf((await client.get(f"/s/{token}")).text)

    owner = await db_session.get(User, 8013)
    owner.settings = {**owner.settings, "paused": True}
    await db_session.commit()

    original = settings.rate_limit_send_per_fingerprint
    settings.rate_limit_send_per_fingerprint = 1
    try:
        blocked = await client.post(f"/s/{token}/send", json={"message": "salom", "csrf_token": csrf})
        assert blocked.status_code == 409
        assert blocked.json() == {"status": "paused", "message": t("sender_paused", "uz")}
        assert (await db_session.execute(select(Message))).scalars().all() == []

        owner = await _reload(db_session, 8013)
        owner.settings = {k: v for k, v in owner.settings.items() if k != "paused"}
        await db_session.commit()

        # budget is 1: if the paused attempt had consumed it, this would be 429
        ok = await client.post(f"/s/{token}/send", json={"message": "salom", "csrf_token": csrf})
        assert ok.status_code == 200 and ok.json()["status"] == "success"
    finally:
        settings.rate_limit_send_per_fingerprint = original


async def test_paused_does_not_change_link_active_or_token(client, db_session, clean_tables):
    link = await _owner(db_session, 8014, "uz", paused=True)
    token = link.token
    await client.get(f"/s/{token}")
    stored = (await db_session.execute(select(PublicLink).where(PublicLink.token == token))).scalars().one()
    assert stored.active is True


# --------------------------------------------------------------------------
# Success screen invitation + anonymous CTA beacon
# --------------------------------------------------------------------------

async def test_success_screen_asks_what_they_would_want_and_reveals_a_plain_bot_link(client, db_session, clean_tables):
    link = await _owner(db_session, 8020)
    page = (await client.get(f"/s/{link.token}")).text
    assert t("sent_ask", "uz") in htmllib.unescape(page)
    cta = re.search(r'<a class="success__cta success__cta--primary" id="ctaOwnLink"[^>]*href="([^"]+)"', page).group(1)
    assert cta == f"https://t.me/{settings.bot_username}"  # served link is plain: no payload, never the token
    assert link.token not in cta
    assert re.search(r'id="ctaWrap" hidden', page)         # CTA stays hidden until a choice is made


def test_success_wording_is_optional_not_pressuring():
    for lang in ("uz", "ru"):
        text = " ".join(t(k, lang) for k in ("sent_ask", "reason_note", "success_cta", "success_cta_hint")).lower()
        for pressure in ("endi navbat", "tez", "shoshil", "bugun", "faqat", "сейчас же", "срочно", "быстрее", "твоя очередь"):
            assert pressure not in text


async def test_cta_beacon_records_an_anonymous_aggregate_event(client, db_session, clean_tables):
    link = await _owner(db_session, 8021)
    resp = await client.post(f"/s/{link.token}/track", json={"name": "sender_cta_clicked"})
    assert resp.json() == {"status": "ok"}
    events = await _events(db_session, "sender_cta_clicked")
    assert len(events) == 1
    assert events[0].user_id is None and events[0].props == {}  # not joinable to a recipient or account


async def test_beacon_still_rejects_unknown_events_and_unknown_tokens(client, db_session, clean_tables):
    link = await _owner(db_session, 8022)
    assert (await client.post(f"/s/{link.token}/track", json={"name": "anything_else"})).json() == {"status": "ignored"}
    assert (await client.post(f"/s/{link.token}/track", json={"name": ["sender_cta_clicked"]})).json() == {"status": "ignored"}
    assert (await client.post("/s/not-a-real-token/track", json={"name": "sender_cta_clicked"})).json() == {"status": "ok"}
    assert await _events(db_session, "sender_cta_clicked") == []


async def test_message_started_beacon_is_unchanged(client, db_session, clean_tables):
    link = await _owner(db_session, 8023)
    await client.post(f"/s/{link.token}/track", json={"name": "message_started"})
    (event,) = await _events(db_session, "message_started")
    assert event.props == {"link_id": link.id} and event.user_id is None


# --------------------------------------------------------------------------
# Wording: integrity promise + precise anonymity claim
# --------------------------------------------------------------------------

async def test_privacy_page_states_the_integrity_promise_in_both_languages(client):
    uz = (await client.get("/privacy")).text
    ru = (await client.get("/privacy?lang=ru")).text
    assert "soxta xabarlar" in uz and "shaxsi hech qachon" in uz  # original closing note preserved
    assert "фейковых сообщений" in ru and "Личность отправителя никогда" in ru


def test_bot_privacy_summary_is_precise_and_includes_the_integrity_promise():
    for lang, must in (("uz", ("hech qachon ko'rsatilmaydi", "xesh", "soxta")), ("ru", ("никогда не показывается", "хеш", "фейков"))):
        text = t("privacy_summary", lang)
        assert all(word in text for word in must)
    # the old absolute claim is gone
    assert "hech qachon oshkor qilmaymiz" not in t("privacy_summary", "uz")


def test_every_new_copy_key_exists_in_both_languages():
    for key in ("sender_paused", "sent_ask", "link_paused_notice", "settings_paused_line", "settings_prompt_btn",
                "settings_pause_btn", "settings_resume_btn", "pause_on_toast", "pause_off_toast",
                "prompt_menu_title", "prompt_saved_toast"):
        assert set(COPY[key]) == {"uz", "ru"} and all(COPY[key].values())


# --------------------------------------------------------------------------
# Bot: pause toggle
# --------------------------------------------------------------------------

def _labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


async def test_settings_screen_offers_pause_then_resume(db_session, clean_tables):
    db_session.add(User(tg_user_id=8030, lang="uz"))
    await db_session.commit()

    msg = FakeMessage(user_id=8030)
    await settings_handlers.on_settings_open_reply_button(msg, db_session)
    assert "settings:pause" in _datas(msg.sent[-1]["reply_markup"])
    assert "settings:resume" not in _datas(msg.sent[-1]["reply_markup"])

    cb = FakeCallbackQuery(user_id=8030, data="settings:pause", message=FakeMessage(user_id=8030))
    await settings_handlers.on_pause(cb, db_session)

    user = await _reload(db_session, 8030)
    assert is_paused(user)
    assert cb.answers == [{"text": t("pause_on_toast", "uz"), "show_alert": False}]
    shown = cb.message.edited[-1]
    assert t("settings_paused_line", "uz") in shown["text"]
    assert "settings:resume" in _datas(shown["reply_markup"]) and "settings:pause" not in _datas(shown["reply_markup"])
    assert len(await _events(db_session, "link_paused")) == 1

    resume = FakeCallbackQuery(user_id=8030, data="settings:resume", message=FakeMessage(user_id=8030))
    await settings_handlers.on_resume(resume, db_session)
    user = await _reload(db_session, 8030)
    assert not is_paused(user) and "paused" not in (user.settings or {})
    assert len(await _events(db_session, "link_resumed")) == 1


async def test_double_tap_is_idempotent_and_records_one_event(db_session, clean_tables):
    db_session.add(User(tg_user_id=8031, lang="uz"))
    await db_session.commit()
    for _ in range(3):
        cb = FakeCallbackQuery(user_id=8031, data="settings:pause", message=FakeMessage(user_id=8031))
        await settings_handlers.on_pause(cb, db_session)
    assert len(await _events(db_session, "link_paused")) == 1
    assert len(cb.message.edited) == 0  # nothing to re-render on a no-op tap


async def test_pause_only_ever_affects_the_tapping_account(db_session, clean_tables):
    db_session.add_all([User(tg_user_id=8032, lang="uz"), User(tg_user_id=8033, lang="uz")])
    await db_session.commit()
    cb = FakeCallbackQuery(user_id=8032, data="settings:pause", message=FakeMessage(user_id=8032))
    await settings_handlers.on_pause(cb, db_session)
    assert is_paused(await _reload(db_session, 8032))
    assert not is_paused(await _reload(db_session, 8033))


async def test_paused_note_shows_on_the_link_screen_and_regenerate_keeps_pause(db_session, clean_tables):
    db_session.add(User(tg_user_id=8034, lang="uz", settings={"paused": True}))
    await db_session.commit()
    await create_link(db_session, owner_user_id=8034)

    msg = FakeMessage(user_id=8034)
    await start_handlers.on_link_show_reply_button(msg, db_session, settings)
    assert t("link_paused_notice", "uz") in msg.sent[-1]["text"]

    cb = FakeCallbackQuery(user_id=8034, data="settings:regenerateconfirm", message=FakeMessage(user_id=8034))
    await settings_handlers.on_regenerate_confirm(cb, db_session, settings)
    assert is_paused(await _reload(db_session, 8034))  # state lives on the account, survives a new link
    assert t("link_paused_notice", "uz") in cb.message.edited[-1]["text"]


async def test_unpaused_link_screen_has_no_paused_note(db_session, clean_tables):
    db_session.add(User(tg_user_id=8035, lang="ru"))
    await db_session.commit()
    msg = FakeMessage(user_id=8035)
    await start_handlers.on_link_show_reply_button(msg, db_session, settings)
    assert t("link_paused_notice", "ru") not in msg.sent[-1]["text"]


# --------------------------------------------------------------------------
# Bot: link line presets
# --------------------------------------------------------------------------

async def test_owner_can_pick_a_preset_and_it_is_what_senders_see(client, db_session, clean_tables):
    link = await _owner(db_session, 8040)
    token = link.token
    cb = FakeCallbackQuery(user_id=8040, data="settings:promptset:birthday", message=FakeMessage(user_id=8040))
    await settings_handlers.on_prompt_set(cb, db_session)

    assert get_prompt_key(await _reload(db_session, 8040)) == "birthday"
    (event,) = await _events(db_session, "prompt_selected")
    assert event.props == {"preset": "birthday"} and event.user_id == 8040
    assert cb.answers[-1]["text"] == t("prompt_saved_toast", "uz")
    assert "✓" in "".join(_labels(cb.message.edited[-1]["reply_markup"]))
    assert line_for("birthday", "uz") in htmllib.unescape((await client.get(f"/s/{token}")).text)


async def test_selecting_default_clears_the_preset(db_session, clean_tables):
    db_session.add(User(tg_user_id=8041, lang="uz", settings={"prompt": "ask"}))
    await db_session.commit()
    cb = FakeCallbackQuery(user_id=8041, data=f"settings:promptset:{DEFAULT_KEY}", message=FakeMessage(user_id=8041))
    await settings_handlers.on_prompt_set(cb, db_session)
    user = await _reload(db_session, 8041)
    assert get_prompt_key(user) == DEFAULT_KEY and "prompt" not in (user.settings or {})


async def test_unknown_callback_values_are_rejected_and_never_stored(db_session, clean_tables):
    db_session.add(User(tg_user_id=8042, lang="uz"))
    await db_session.commit()
    for evil in ("<b>x</b>", "ask:extra", "../x", "", "ASK", "birthday ", "a" * 200):
        cb = FakeCallbackQuery(user_id=8042, data=f"settings:promptset:{evil}", message=FakeMessage(user_id=8042))
        await settings_handlers.on_prompt_set(cb, db_session)
        assert cb.answers[-1] == {"text": t("generic_error", "uz"), "show_alert": True}
    user = await _reload(db_session, 8042)
    assert "prompt" not in (user.settings or {})
    assert await _events(db_session, "prompt_selected") == []


async def test_reselecting_the_same_preset_records_no_new_event(db_session, clean_tables):
    db_session.add(User(tg_user_id=8043, lang="ru"))
    await db_session.commit()
    for _ in range(2):
        cb = FakeCallbackQuery(user_id=8043, data="settings:promptset:advice", message=FakeMessage(user_id=8043))
        await settings_handlers.on_prompt_set(cb, db_session)
    assert len(await _events(db_session, "prompt_selected")) == 1


async def test_prompt_menu_lists_every_preset_default_and_back(db_session, clean_tables):
    db_session.add(User(tg_user_id=8044, lang="uz", settings={"prompt": "memory"}))
    await db_session.commit()
    cb = FakeCallbackQuery(user_id=8044, data="settings:prompt", message=FakeMessage(user_id=8044))
    await settings_handlers.on_prompt_menu(cb, db_session)
    markup = cb.message.edited[-1]["reply_markup"]
    assert cb.message.edited[-1]["text"] == t("prompt_menu_title", "uz")
    datas = _datas(markup)
    assert [d for d in datas if d.startswith("settings:promptset:")] == [f"settings:promptset:{k}" for k in PRESET_KEYS] + [f"settings:promptset:{DEFAULT_KEY}"]
    assert "settings:open" in datas
    assert sum(label.startswith("✓") for label in _labels(markup)) == 1  # only the active one is marked


def test_keyboards_respect_telegram_callback_data_limits():
    for lang in ("uz", "ru"):
        for markup in (settings_keyboard(lang), settings_keyboard(lang, paused=True), prompt_keyboard(lang, DEFAULT_KEY)):
            for data in _datas(markup):
                assert len(data.encode()) <= 64
