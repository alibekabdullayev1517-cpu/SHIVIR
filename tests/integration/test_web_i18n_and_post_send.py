"""Sender web UX: UZ/RU end to end, Unicode recipient names, and the post-send
"what would you want to receive?" flow (real choice -> real deep link -> real preset)."""

import re
from pathlib import Path

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select

from bot.handlers import start
from core.config import get_settings
from core.copy import COPY, t
from core.link_prompts import PRESET_KEYS, SENDER_REASON_KEYS, line_for
from core.models import Event, User
from core.services.links import clean_display_name, create_link, get_prompt_key
from tests.fakes import FakeMessage

settings = get_settings()
ROOT = Path(__file__).resolve().parents[2]
CYRILLIC = re.compile("[А-Яа-яЁёЎўҚқҒғҲҳӮӯӢӣҶҷ]")


@pytest_asyncio.fixture
async def client(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


async def _owner(db, tg_id, lang="uz", name=None):
    st = {"display_name": name} if name is not None else {}
    db.add(User(tg_user_id=tg_id, lang=lang, settings=st))
    await db.commit()
    return await create_link(db, owner_user_id=tg_id)


def _visible(html: str) -> str:
    """Page text without script/style, tags and entities — what a person could read."""
    import html as htmllib

    body = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", body))


# --- language: UZ, RU, override, persistence ---------------------------------

async def test_uzbek_sender_page_uses_the_agreed_informal_copy(client, db_session, clean_tables):
    link = await _owner(db_session, 9801, "uz", "Ali")
    html = (await client.get(f"/s/{link.token}")).text
    text = _visible(html)
    for expected in ("Nima deging kelyapti?", "Yuborish", "Oluvchi kim yozganini bilmaydi.", "Maxfiylik siyosati"):
        assert expected in text
    assert 'placeholder="Xabaringni yoz..."' in html
    assert "Ali uchun anonim xabar" in html          # the composer's accessible label
    assert not CYRILLIC.search(text)                  # no Russian anywhere on the Uzbek page
    assert '<html lang="uz">' in html


async def test_russian_sender_page_is_fully_russian_and_informal(client, db_session, clean_tables):
    link = await _owner(db_session, 9802, "ru", "Аброр")
    html = (await client.get(f"/s/{link.token}")).text
    text = _visible(html)
    for expected in ("Что хочется сказать?", "Отправить", "Получатель не узнает, кто ты.", "Политика конфиденциальности"):
        assert expected in text
    assert 'placeholder="Напиши сообщение..."' in html
    assert "Анонимное сообщение для Аброр" in html
    for uzbek in ("Yuborish", "Maxfiylik", "Xabaring", "anonim xabar", "Oluvchi"):
        assert uzbek not in text
    assert '<html lang="ru">' in html


async def test_lang_param_beats_the_owner_language_and_bad_values_are_ignored(client, db_session, clean_tables):
    link = await _owner(db_session, 9803, "uz", "Ali")
    ru = (await client.get(f"/s/{link.token}?lang=ru")).text
    assert '<html lang="ru">' in ru and "Отправить" in _visible(ru)
    bad = (await client.get(f"/s/{link.token}?lang=de")).text
    assert '<html lang="uz">' in bad                                     # unsupported -> owner's language
    link2 = await _owner(db_session, 9804, "ru", "Ali")
    uz = (await client.get(f"/s/{link2.token}?lang=uz")).text
    assert '<html lang="uz">' in uz and "Yuborish" in _visible(uz)


async def test_language_switch_links_and_persistence_across_pages(client, db_session, clean_tables):
    link = await _owner(db_session, 9805, "uz", "Ali")
    page = (await client.get(f"/s/{link.token}?lang=ru")).text
    assert f'href="/s/{link.token}?lang=uz"' in page and f'href="/s/{link.token}?lang=ru"' in page
    assert re.search(r'lang="ru"[^>]*>RU<', page) is None or 'aria-current="true"' in page
    # the privacy link carries the chosen language and a way back
    privacy = re.search(r'href="(/privacy\?[^"]+)"', page).group(1).replace("&amp;", "&")
    assert privacy == f"/privacy?lang=ru&back=/s/{link.token}"
    policy = (await client.get(privacy)).text
    assert "Политика конфиденциальности" in policy and '<html lang="ru">' in policy
    assert f'href="/s/{link.token}?lang=ru"' in policy                       # back returns in Russian
    # switching language on the policy keeps the (validated) back target
    assert f'href="/privacy?lang=uz&amp;back=%2Fs%2F{link.token}"' in policy


async def test_privacy_page_in_both_languages_keeps_its_content(client, clean_tables):
    from web.routes.legal import PARAGRAPHS

    for lang, title in (("uz", "Maxfiylik siyosati"), ("ru", "Политика конфиденциальности")):
        text = _visible((await client.get(f"/privacy?lang={lang}")).text)
        assert title in text
        assert PARAGRAPHS[lang][0].split()[0] in text and PARAGRAPHS[lang][-1] in text
    assert "100%" not in _visible((await client.get("/privacy?lang=uz")).text)


async def test_privacy_back_link_only_ever_points_at_a_sender_page(client, clean_tables):
    for evil in ("https://evil.example", "//evil.example", "javascript:alert(1)", "/admin", "/s/../etc", "/s/a b"):
        page = (await client.get("/privacy", params={"lang": "uz", "back": evil})).text
        assert "evil.example" not in page and "javascript:" not in page and 'class="link backlink' not in page
    ok = (await client.get("/privacy", params={"lang": "uz", "back": "/s/abcDEF123"})).text
    assert 'href="/s/abcDEF123?lang=uz"' in ok


async def test_invalid_link_page_is_localized_and_has_the_switch(client, clean_tables):
    ru = await client.get("/s/nope-nope-1?lang=ru")
    assert ru.status_code == 404 and t("link_invalid", "ru") in ru.text and 'class="langswitch' in ru.text
    uz = await client.get("/s/nope-nope-1")
    assert t("link_invalid", "uz") in uz.text


def test_web_copy_is_one_register_per_language():
    keys = ("sender_hint", "sender_assurance", "compose_label", "compose_label_named", "chars_limit_reached",
            "compose_placeholder", "send_success", "sent_title", "sent_reassurance", "rate_limited",
            "abuse_warning_prompt", "web_error", "web_offline", "sent_ask", "reason_note", "success_cta")
    for key in keys:
        assert set(COPY[key]) == {"uz", "ru"} and all(COPY[key].values())
        uz, ru = COPY[key]["uz"].lower(), COPY[key]["ru"].lower()
        assert not re.search(r"ingiz|ing\b(?!a)|\bsiz", uz.replace("deging", "").replace("ko'ring", "X")) or "ko'ring" not in uz
        assert "ingiz" not in uz and "yozing" not in uz and "yuboring" not in uz
        assert not re.search(r"\b(вы|вас|вам|ваш\w*|напишите|попробуйте|отправьте)\b", ru)
    for key in PRESET_KEYS:  # the lines senders read on the page follow the same register
        assert "ingiz" not in line_for(key, "uz").lower() and "ите" not in line_for(key, "ru").lower().split()[0]


# --- Unicode recipient names / the glyph problem ------------------------------

def test_name_cleaning_removes_only_what_cannot_render():
    assert clean_display_name("Аброр") == "Аброр"                  # Apple-logo private-use glyph (the real case)
    assert clean_display_name("") is None and clean_display_name("   ") is None and clean_display_name(None) is None
    assert clean_display_name("Ali‮evil") == "Alievil"              # bidi override
    assert clean_display_name("A​B") == "AB"                        # zero-width space
    assert clean_display_name("Аброр  \n ҳақ") == "Аброр ҳақ"            # whitespace collapsed
    for keep in ("Ўткир Қодиров", "Ғулом Ҳамид", "Oʻktam G‘ulom", "Мария-Анна", "Ali 🙂", "👨‍👩‍👧 Oila", "🇺🇿 Vatan"):
        assert clean_display_name(keep) == keep
    long = clean_display_name("Ж" * 200)
    assert len(long) == 41 and long.endswith("…")


async def test_unicode_recipient_names_render_correctly_and_are_escaped(client, db_session, clean_tables):
    cases = {
        9811: "Ўткир Қодиров Ғулом Ҳамид",         # Uzbek Cyrillic: ў қ ғ ҳ
        9812: "Oʻktam Gʻulom",                       # Uzbek Latin modifier letters
        9813: "Аброр",                          # unrenderable glyph in the real data
        9814: "Ali 🙂 Vali",                          # emoji
        9815: "<b>x</b>&\"'",                         # markup is escaped
    }
    for tg, name in cases.items():
        link = await _owner(db_session, tg, "uz", name)
        html = (await client.get(f"/s/{link.token}")).text
        h1 = re.search(r'<h1 class="recipient__name" id="recipientName">(.*?)</h1>', html, re.S).group(1)
        assert "" not in html and "�" not in html
        if tg == 9815:
            assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in h1
        else:
            expected = clean_display_name(name)
            assert h1 == expected, (h1, expected)
        # the stored value is never rewritten by rendering
        assert (await db_session.get(User, tg)).settings["display_name"] == name


async def test_long_names_are_capped_and_unbreakable_names_can_wrap(client, db_session, clean_tables):
    link = await _owner(db_session, 9816, "ru", "А" * 120)
    html = (await client.get(f"/s/{link.token}")).text
    h1 = re.search(r'id="recipientName">(.*?)</h1>', html, re.S).group(1)
    assert len(h1) == 41 and h1.endswith("…")
    css = (ROOT / "web/static/style.css").read_text()
    assert re.search(r"\.recipient__name \{[^}]*overflow-wrap: anywhere", css, re.S)


async def test_page_without_a_usable_name_falls_back_to_the_headline(client, db_session, clean_tables):
    link = await _owner(db_session, 9817, "uz", "")
    html = (await client.get(f"/s/{link.token}")).text
    assert re.search(r'id="recipientName">Nima deging kelyapti\?</h1>', html)


async def test_cyrillic_extended_font_is_shipped_declared_and_served(client, clean_tables):
    css = (ROOT / "web/static/style.css").read_text()
    face = re.search(r'@font-face \{[^}]*inter-cyrillic-ext-wght-normal\.woff2[^}]*unicode-range: ([^;]+);', css, re.S)
    assert face, "the Cyrillic Extended @font-face is missing"
    ranges = face.group(1)
    assert "U+0460-052F" in ranges                        # covers қ U+049B, ғ U+0493, ҳ U+04B3, ӯ U+04EF, ӣ U+04E3, ҷ U+04B7
    for cp in (0x049B, 0x0493, 0x04B3, 0x04EF, 0x04E3, 0x04B7):
        assert 0x0460 <= cp <= 0x052F
    assert "Noto Color Emoji" in css and "Apple Color Emoji" in css       # emoji fallback stays in the stack
    resp = await client.get("/static/fonts/inter-cyrillic-ext-wght-normal.woff2")
    assert resp.status_code == 200 and resp.content[:4] == b"wOF2" and len(resp.content) < 60_000


# --- post-send flow -----------------------------------------------------------

async def test_success_view_offers_the_four_real_choices_in_both_languages(client, db_session, clean_tables):
    labels = {"uz": ["💬 Savol", "💛 Iliq gap", "💡 Maslahat", "😄 Hazil"],
              "ru": ["💬 Вопрос", "💛 Тёплые слова", "💡 Совет", "😄 Шутка"]}
    for tg, lang in ((9821, "uz"), (9822, "ru")):
        link = await _owner(db_session, tg, lang, "Ali")
        html = (await client.get(f"/s/{link.token}")).text
        view = html[html.index('id="successView"'):html.index('id="pausedView"')]
        assert re.findall(r'data-reason="(\w+)"', view) == list(SENDER_REASON_KEYS) == ["ask", "compliment", "advice", "funny"]
        assert re.findall(r'<button[^>]*class="reason"[^>]*>\s*<span>(.*?)</span>', view) == labels[lang]
        assert view.count('aria-pressed="false"') == 4
        import html as htmllib

        shown = htmllib.unescape(html)
        assert t("sent_ask", lang) in htmllib.unescape(view) and t("success_cta", lang) in shown and t("success_cta_hint", lang) in shown
        assert 'id="ctaWrap" hidden' in view                       # revealed only after a choice
        assert 'aria-live="polite"' in view                        # the note under the choices is announced
        # Selection JS: builds the deep link from a fixed key, marks the choice by state (aria-pressed) not colour alone
        assert '"?start=r_" + encodeURIComponent(chosenReason)' in html
        assert 'name: "post_send_view"' in html or 'beacon("post_send_view")' in html


def test_selected_state_is_not_colour_only():
    css = (ROOT / "web/static/style.css").read_text()
    assert re.search(r'\.reason\[aria-pressed="true"\] \.reason__check \{ display: block; \}', css)   # a check mark
    assert re.search(r"\.reasons\[data-chosen\] \.reason:not\(\[aria-pressed=\"true\"\]\) \{ opacity", css)
    assert "prefers-reduced-motion" in css


async def test_sending_and_the_200_limit_still_work_with_the_new_screen(client, db_session, clean_tables):
    from tests.integration.test_track_rate_limit import _csrf

    link = await _owner(db_session, 9823, "uz", "Ali")
    page = await client.get(f"/s/{link.token}")
    assert 'maxlength="200"' in page.text
    ok = await client.post(f"/s/{link.token}/send", json={"message": "salom", "csrf_token": _csrf(page.text)})
    assert ok.json()["status"] == "success"
    from core.services.messages import MAX_MESSAGE_LENGTH

    too_long = await client.post(
        f"/s/{link.token}/send", json={"message": "x" * (MAX_MESSAGE_LENGTH + 1), "csrf_token": _csrf(page.text)}
    )
    assert too_long.status_code == 422 and too_long.json()["status"] == "validation_error"


# --- analytics ---------------------------------------------------------------

async def _events(db, name):
    return (await db.execute(select(Event).where(Event.name == name))).scalars().all()


async def test_post_send_view_and_reason_selected_are_anonymous_and_allow_listed(client, db_session, clean_tables):
    link = await _owner(db_session, 9831, "uz", "Ali")
    url = f"/s/{link.token}/track"
    assert (await client.post(url, json={"name": "post_send_view"})).json() == {"status": "ok"}
    for reason in SENDER_REASON_KEYS:
        assert (await client.post(url, json={"name": "reason_selected", "reason": reason})).json() == {"status": "ok"}
    (view,) = await _events(db_session, "post_send_view")
    assert view.user_id is None and view.props == {}
    chosen = await _events(db_session, "reason_selected")
    assert sorted(e.props["reason"] for e in chosen) == sorted(SENDER_REASON_KEYS)
    assert all(e.user_id is None and set(e.props) == {"reason"} for e in chosen)


async def test_reason_must_be_one_of_the_four_fixed_keys(client, db_session, clean_tables):
    link = await _owner(db_session, 9832, "uz", "Ali")
    url = f"/s/{link.token}/track"
    for bad in ({"name": "reason_selected"}, {"name": "reason_selected", "reason": "honest"},
                {"name": "reason_selected", "reason": "<script>"}, {"name": "reason_selected", "reason": ["ask"]},
                {"name": "reason_selected", "reason": {"a": 1}}, {"name": "reason_selected", "reason": "x" * 500}):
        assert (await client.post(url, json=bad)).json() == {"status": "ignored"}
    assert await _events(db_session, "reason_selected") == []
    # on the CTA event a bad reason is simply dropped; the click itself is still counted, anonymously
    await client.post(url, json={"name": "sender_cta_clicked", "reason": "<script>"})
    await client.post(url, json={"name": "sender_cta_clicked", "reason": "funny"})
    await client.post(url, json={"name": "sender_cta_clicked"})
    props = sorted((e.props for e in await _events(db_session, "sender_cta_clicked")), key=str)
    assert props == sorted([{}, {}, {"reason": "funny"}], key=str) and all(e.user_id is None for e in await _events(db_session, "sender_cta_clicked"))


async def test_message_sent_analytics_is_unchanged(client, db_session, clean_tables):
    from tests.integration.test_track_rate_limit import _csrf

    link = await _owner(db_session, 9833, "uz", "Ali")
    page = await client.get(f"/s/{link.token}")
    await client.post(f"/s/{link.token}/send", json={"message": "salom", "csrf_token": _csrf(page.text)})
    (sent,) = await _events(db_session, "message_sent")
    assert sent.user_id is None and set(sent.props) == {"link_id", "char_count"}


# --- the choice is real: Telegram deep link -> preset on the new account --------

async def _start(db, tg_id, text, name="Ali"):
    msg = FakeMessage(user_id=tg_id, text=text)
    msg.from_user.first_name = name
    await start.cmd_start(msg, db, settings)
    return msg


async def test_new_account_from_a_reason_deep_link_gets_that_line_on_its_first_link(db_session, clean_tables):
    for i, key in enumerate(SENDER_REASON_KEYS):
        tg = 9840 + i
        await _start(db_session, tg, f"/start r_{key}")
        user = await db_session.get(User, tg)
        assert get_prompt_key(user) == key
        assert line_for(key, "uz") and line_for(key, "ru")            # a real, localized line exists for every choice
    started = (await db_session.execute(select(Event).where(Event.name == "bot_started", Event.user_id == 9840))).scalars().one()
    assert started.props["reason"] == "ask" and started.props["source"] == "deep_link"


async def test_deep_link_payloads_that_are_not_a_sender_reason_change_nothing(db_session, clean_tables):
    for tg, payload in ((9850, "/start r_honest"), (9851, "/start r_nope"), (9852, "/start r_"),
                        (9853, "/start ask"), (9854, "/start r_ask; drop"), (9855, "/start")):
        await _start(db_session, tg, payload)
        assert get_prompt_key(await db_session.get(User, tg)) == "none"


async def test_existing_accounts_are_never_overwritten_by_a_deep_link(db_session, clean_tables):
    db_session.add(User(tg_user_id=9860, lang="uz", settings={"prompt": "birthday"}))
    await db_session.commit()
    await _start(db_session, 9860, "/start r_funny")
    assert get_prompt_key(await db_session.get(User, 9860)) == "birthday"


def test_every_preset_is_localized_and_the_hazil_preset_exists():
    assert "funny" in PRESET_KEYS
    assert "Hazil" in COPY["reason_funny"]["uz"] and "Шутка" in COPY["reason_funny"]["ru"]


def test_every_copy_key_the_code_asks_for_exists():
    """t("x", lang) silently returns "x" for an unknown key — the visitor would read the key name.
    Scan the source for literal keys (and the reason_<key> pattern) so a lost key fails a test."""
    used = set()
    for folder in ("web", "bot", "core", "workers"):
        for path in (ROOT / folder).rglob("*.py"):
            used |= set(re.findall(r'\bt\(\s*"([a-z0-9_]+)"', path.read_text()))
    used |= {f"reason_{key}" for key in SENDER_REASON_KEYS}
    missing = sorted(k for k in used if k not in COPY)
    assert not missing, f"copy keys used but not defined: {missing}"
    assert {"send_cta", "prompts_label"} <= set(COPY)
