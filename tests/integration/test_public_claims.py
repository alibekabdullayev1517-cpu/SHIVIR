"""Public privacy/integrity claims must be exactly supportable by the implementation.

Each test pins one statement the product makes to people (privacy page, bot privacy
summary, sender screens) to the code/config/storage behaviour that makes it true. If
behaviour changes, the test fails and the wording has to be revisited — not the reverse.
"""

import re
from pathlib import Path

import httpx
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import select, text

from core.config import get_settings
from core.copy import COPY, t
from core.models import Block, Event, Message, User
from core.safety import lexicon_uz
from core.security import compute_fingerprint
from core.services.links import create_link
from core.services.messages import send_message
from web.routes.legal import PARAGRAPHS

from bot.handlers import inbox
from tests.fakes import FakeBot, FakeCallbackQuery, FakeMessage
from workers.notifier import _deliver

settings = get_settings()
ROOT = Path(__file__).resolve().parents[2]
SECRET_FP = "cafebabedeadbeef" * 2


@pytest_asyncio.fixture
async def client(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


def _csrf(html: str) -> str:
    return re.search(r'const csrfToken = "([^"]+)"', html).group(1)


async def _link(db_session, tg_id: int, lang: str = "uz"):
    db_session.add(User(tg_user_id=tg_id, lang=lang))
    await db_session.commit()
    return await create_link(db_session, owner_user_id=tg_id)


# ---------------------------------------------------------------------------
# Wording: equivalence + no overstatement
# ---------------------------------------------------------------------------

# (uz marker, ru marker) that must appear in the paragraph at the same position in both languages
_EQUIVALENT_FACTS = {
    1: [("ismi va tili", "имя и язык"), ("Telegram hisobiga bog'lanmaydi", "ни с одним аккаунтом")],
    2: [("xesh", "хеш"), ("tiklab bo'lmaydi", "нельзя восстановить"), ("bog'lanishi mumkin", "связываться")],
    3: [("ikki hafta", "двух недель"), ("uzoq muddatli jurnali yuritilmaydi", "долгосрочный журнал"),
        ("IP-manzilini bilib olishi texnik jihatdan mumkin", "узнать IP-адрес отправителя")],  # operator-side limitation
    4: [("zaxira", "резервн"), ("avtomatik o'chirilmaydi", "автоматически не удаляются")],
    5: [("bloklagan", "заблокировал"), ("yetkazilmasligi mumkin", "не доставлено")],
    6: [("to'qimaydi", "выдумывает"), ("soxta bildirishnomalar", "уведомлений")],
    7: [("hech qachon", "никогда")],
}


def test_uzbek_and_russian_privacy_pages_make_the_same_statements():
    uz, ru = PARAGRAPHS["uz"], PARAGRAPHS["ru"]
    assert len(uz) == len(ru) == 8
    for index, pairs in _EQUIVALENT_FACTS.items():
        for uz_marker, ru_marker in pairs:
            assert uz_marker in uz[index], (index, uz_marker)
            assert ru_marker in ru[index], (index, ru_marker)


_OVERSTATEMENTS = (
    "100%", "100 %", "untrace", "izsiz", "mutlaqo", "to'liq anonim", "butunlay o'chiriladi",
    "faqat zarur muddatga", "shaxsga bog'liq bo'lmagan", "hech kim bilmaydi", "biz ham bilmaymiz",
    "полностью аноним", "абсолютно", "невозможно узнать", "удаляется полностью",
    "только на необходимый срок", "обезличенн", "даже мы", "even by us",
)


def _public_texts() -> list[str]:
    keys = ("privacy_summary", "safety_summary", "sender_hint", "sender_assurance", "sent_reassurance",
            "send_success", "sent_title", "sender_paused", "sent_invite", "link_ready_title",
            "welcome_body", "report_confirmation", "block_confirmation")
    texts = [COPY[k][lang] for k in keys for lang in ("uz", "ru")]
    texts += PARAGRAPHS["uz"] + PARAGRAPHS["ru"]
    return texts


def test_no_public_text_overstates_anonymity_or_retention():
    for text_ in _public_texts():
        lowered = text_.lower()
        for phrase in _OVERSTATEMENTS:
            assert phrase.lower() not in lowered, f"{phrase!r} in: {text_[:80]}"


def test_bot_summary_and_page_agree_on_what_is_stored():
    for lang, hash_word, log_word in (("uz", "xesh", "jurnal"), ("ru", "хеш", "журнал")):
        summary = t("privacy_summary", lang).lower()
        assert hash_word in summary and log_word in summary  # names the hash AND the web-server log caveat
        assert "faqat bir tomonlama xesh saqlanadi" not in summary  # the earlier, overstated wording


def test_retention_wording_is_tied_to_the_actual_backup_and_log_settings():
    """The page says "about two weeks". Backups: RETENTION_DAYS default 14. Logs: deploy
    doc pins logrotate at 14. If someone changes either, this fails and the page must follow."""
    assert 'RETENTION_DAYS="${RETENTION_DAYS:-14}"' in (ROOT / "infra" / "backup.sh").read_text()
    deploy = (ROOT / "infra" / "DEPLOYMENT.md").read_text()
    assert "rotate 14" in deploy and "Keep the public privacy page true" in deploy
    assert "ikki hafta" in PARAGRAPHS["uz"][3] and "ikki hafta" in PARAGRAPHS["uz"][4]
    assert "двух недель" in PARAGRAPHS["ru"][3] and "двух недель" in PARAGRAPHS["ru"][4]


# ---------------------------------------------------------------------------
# "Sender identity is never shown to the recipient"
# ---------------------------------------------------------------------------

async def test_nothing_the_recipient_can_open_contains_sender_identifiers(db_session, fake_redis, clean_tables):
    link = await _link(db_session, 9601)
    message_id = (await send_message(
        db_session, fake_redis, settings, link_id=link.id, link_active=True, recipient_user_id=9601,
        body="Salom, qalaysan?", fingerprint_hash=SECRET_FP,
    )).message_id

    detail = FakeCallbackQuery(user_id=9601, data=f"msg:open:{message_id}", message=FakeMessage(user_id=9601))
    await inbox.on_message_open(detail, db_session)
    inbox_cb = FakeCallbackQuery(user_id=9601, data="inbox:open", message=FakeMessage(user_id=9601))
    await inbox.on_inbox_open(inbox_cb, db_session, settings)

    surfaces = [str(e) for cb in (detail, inbox_cb) for e in cb.message.edited]
    assert surfaces and all(SECRET_FP not in s and "fingerprint" not in s.lower() for s in surfaces)
    shown = detail.message.edited[-1]["text"]
    assert re.fullmatch(r"Salom, qalaysan\?\n\n\d{4}-\d\d-\d\d \d\d:\d\d", shown)  # text + minute-precision time only

    bot = FakeBot()
    await _deliver(bot, db_session, message_id)  # the only unsolicited Telegram send about a message
    assert [m["text"] for m in bot.sent] == [t("new_message_notification", "uz")]  # generic: no text, no sender


# ---------------------------------------------------------------------------
# "Only a one-way hash is kept in the database; no raw IP anywhere in it"
# ---------------------------------------------------------------------------

async def test_no_raw_ip_or_user_agent_is_stored_in_any_table(client, db_session, fake_redis, clean_tables):
    ip, ua = "203.0.113.77", "ProbeBrowser/9.9 (ClaimTest)"
    link = await _link(db_session, 9602)
    token = link.token
    headers = {"x-forwarded-for": ip, "user-agent": ua}
    page = await client.get(f"/s/{token}", headers=headers)
    await client.post(f"/s/{token}/track", json={"name": "message_started"}, headers=headers)
    sent = await client.post(
        f"/s/{token}/send", json={"message": "Bugun ob-havo yaxshi", "csrf_token": _csrf(page.text)}, headers=headers
    )
    assert sent.json()["status"] == "success"

    expected = compute_fingerprint(settings.secret_key, ip, ua)
    (stored,) = (await db_session.execute(select(Message))).scalars().all()
    assert stored.sender_fingerprint_hash == expected and len(expected) == 32
    assert ip not in expected and "ProbeBrowser" not in expected

    # dump every application table as text and look for the raw values
    for table in ("users", "public_links", "messages", "blocks", "reports", "moderation_actions", "events"):
        rows = (await db_session.execute(text(f"SELECT * FROM {table}"))).all()
        dump = " ".join(str(r) for r in rows)
        assert ip not in dump and "ProbeBrowser" not in dump, table
    # redis (rate-limit counters + queue) holds only the hash too
    keys = " ".join([k async for k in fake_redis.scan_iter("*")])
    assert ip not in keys and "ProbeBrowser" not in keys and expected in keys


async def test_sender_side_events_are_not_linked_to_any_account(client, db_session, clean_tables):
    link = await _link(db_session, 9603)
    token = link.token
    page = await client.get(f"/s/{token}")
    await client.post(f"/s/{token}/track", json={"name": "message_started"})
    await client.post(f"/s/{token}/send", json={"message": "salom", "csrf_token": _csrf(page.text)})
    events = (await db_session.execute(select(Event).where(Event.name.in_(
        ["link_clicked", "sender_page_viewed", "message_started", "message_sent"])))).scalars().all()
    assert {e.name for e in events} == {"link_clicked", "sender_page_viewed", "message_started", "message_sent"}
    assert all(e.user_id is None for e in events)
    assert all(set(e.props) <= {"link_id", "token", "char_count"} for e in events)


# ---------------------------------------------------------------------------
# "A blocked or filtered message may not be delivered" (sender-facing disclosure)
# ---------------------------------------------------------------------------

async def test_blocked_senders_see_success_but_nothing_is_delivered(client, db_session, clean_tables):
    ip, ua = "198.51.100.5", "BlockedBrowser/1.0"
    link = await _link(db_session, 9604)
    token = link.token
    db_session.add(Block(user_id=9604, sender_fingerprint_hash=compute_fingerprint(settings.secret_key, ip, ua)))
    await db_session.commit()
    headers = {"x-forwarded-for": ip, "user-agent": ua}
    page = await client.get(f"/s/{token}", headers=headers)
    sent = await client.post(f"/s/{token}/send", json={"message": "salom", "csrf_token": _csrf(page.text)}, headers=headers)
    assert sent.json()["status"] == "success"                      # the sender sees a normal confirmation…
    assert (await db_session.execute(select(Message))).scalars().all() == []   # …but nothing was stored or delivered
    assert "bloklagan" in PARAGRAPHS["uz"][5]                         # and the privacy page says so


async def test_severe_messages_are_confirmed_to_the_sender_but_not_delivered(client, db_session, fake_redis, clean_tables):
    link = await _link(db_session, 9605)
    token = link.token
    page = await client.get(f"/s/{token}")
    threat = f"{lexicon_uz.THREAT[0]} seni"
    body = {"message": threat, "csrf_token": _csrf(page.text), "acknowledge_warning": True}
    assert (await client.post(f"/s/{token}/send", json=body)).json()["status"] == "success"
    (stored,) = (await db_session.execute(select(Message))).scalars().all()
    assert stored.deleted_at is not None and stored.body == ""          # auto-removed pending review
    assert await fake_redis.llen("shivir:notify:queue") == 0            # and no notification is queued for it
    assert "xavfsizlik" in PARAGRAPHS["uz"][5]


# ---------------------------------------------------------------------------
# "Shivir does not invent messages, notifications or sender hints"
# ---------------------------------------------------------------------------

def _python_files(*dirs: str):
    for d in dirs:
        yield from (p for p in (ROOT / d).rglob("*.py") if "__pycache__" not in p.parts)


def test_the_only_code_that_creates_a_message_is_the_real_sender_path():
    """`Message(` (the DB model) is constructed in exactly one place: the sender pipeline.
    aiogram's Message is only ever a type annotation / handler argument, never constructed."""
    creators = set()
    for path in _python_files("core", "bot", "web", "workers", "cards"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.search(r"(?<![A-Za-z_.])Message\(", line) and "class Message" not in line:
                creators.add(str(path.relative_to(ROOT)))
    assert creators == {"core/services/messages.py"}


def test_the_only_unsolicited_telegram_sends_are_the_real_message_notification_and_error_reply():
    senders = set()
    for path in _python_files("core", "bot", "web", "workers", "cards"):
        if re.search(r"\.(send_message|send_photo|send_document|copy_message|forward_message)\(", path.read_text(encoding="utf-8")):
            senders.add(str(path.relative_to(ROOT)))
    assert senders == {"workers/notifier.py", "bot/error_handler.py"}


async def test_no_notification_is_sent_for_a_message_that_does_not_exist_or_was_deleted(db_session, fake_redis, clean_tables):
    link = await _link(db_session, 9606)
    message_id = (await send_message(
        db_session, fake_redis, settings, link_id=link.id, link_active=True, recipient_user_id=9606,
        body="salom", fingerprint_hash="1" * 32,
    )).message_id
    bot = FakeBot()
    await _deliver(bot, db_session, 987654)  # no such message
    m = await db_session.get(Message, message_id)
    m.body, m.deleted_at = "", m.created_at
    await db_session.commit()
    await _deliver(bot, db_session, message_id)
    assert bot.sent == []
