"""/stats — admin-only, aggregate-only, Uzbek-only daily report (text + PNG)."""

import io
import re
from datetime import datetime, timedelta, timezone

from PIL import Image
from sqlalchemy import func, select

from bot.handlers import moderation
from cards.stats_render import render_stats_card
from core.config import get_settings
from core.models import Event, Message, PublicLink, User
from core.services.stats import ACTIVE_EVENTS, collect_stats, local_today, report_uz, summary_uz
from tests.fakes import FakeMessage

settings = get_settings()
ADMIN = 999999999

# 21 Sep 2026, 10:00 in Tashkent (UTC+5, no DST) — a local day that starts 20 Sep 19:00 UTC.
NOW = datetime(2026, 9, 21, 5, 0, tzinfo=timezone.utc)
DAY_START = datetime(2026, 9, 20, 19, 0, tzinfo=timezone.utc)
SECOND = timedelta(seconds=1)


async def _user(db, uid, created=NOW):
    db.add(User(tg_user_id=uid, lang="uz", created_at=created))
    await db.commit()


async def _event(db, name, uid, at=NOW):
    db.add(Event(name=name, user_id=uid, props={}, created_at=at))
    await db.commit()


async def _link(db, owner, at=NOW, active=True):
    link = PublicLink(owner_user_id=owner, created_at=at, active=active)
    db.add(link)
    await db.commit()
    return link


async def _message(db, link, at=NOW):
    db.add(Message(link_id=link.id, recipient_user_id=link.owner_user_id, body="SECRETBODY-do-not-leak",
                   created_at=at, sender_fingerprint_hash="f" * 32))
    await db.commit()


async def _stats(db):
    return await collect_stats(db, now=NOW)


# --- handler / authorization -------------------------------------------------

async def test_admin_gets_uzbek_text_then_one_png(db_session, clean_tables):
    msg = FakeMessage(user_id=ADMIN, text="/stats")
    await moderation.cmd_stats(msg, db_session, settings)
    assert len(msg.sent) == 1 and len(msg.photos) == 1
    assert msg.sent[0]["text"].startswith("📊 SHIVIR — Bugungi statistika")
    png = msg.photos[0]["photo"].data
    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG" and image.size == (1080, 1350)


async def test_non_admin_gets_nothing_like_modqueue(db_session, clean_tables):
    msg = FakeMessage(user_id=123, text="/stats")
    await moderation.cmd_stats(msg, db_session, settings)
    other = FakeMessage(user_id=123, text="/modqueue")
    await moderation.cmd_modqueue(other, db_session, settings)
    assert msg.sent == msg.photos == [] and other.sent == other.photos == []


async def test_stats_command_records_nothing_and_admin_is_not_made_active(db_session, clean_tables):
    await _user(db_session, ADMIN, created=NOW - timedelta(days=90))
    before = (await db_session.execute(select(func.count(Event.id)))).scalar_one()
    msg = FakeMessage(user_id=ADMIN, text="/stats")
    await moderation.cmd_stats(msg, db_session, settings)
    await moderation.cmd_modqueue(FakeMessage(user_id=ADMIN, text="/modqueue"), db_session, settings)
    assert (await db_session.execute(select(func.count(Event.id)))).scalar_one() == before == 0
    s = await collect_stats(db_session)
    assert (s.active_1, s.active_7, s.active_30) == (0, 0, 0)


async def test_report_is_uzbek_only_and_matches_the_template(db_session, clean_tables):
    text = report_uz(await _stats(db_session))
    for heading in ("👥 FOYDALANUVCHILAR", "🔗 HAVOLALAR", "💬 XABARLAR", "📈 O‘SISH", "💡 XULOSA",
                    "Yangi foydalanuvchilar:", "Faol foydalanuvchilar (7 kun):", "Faol foydalanuvchilar (30 kun):",
                    "Bugun yaratilgan:", "Jami:", "7 kun:"):
        assert heading in text
    assert not re.search("[А-Яа-яЁё]", text)
    assert not re.search(r"\b(users?|active|total|today|new|messages?|links?|days?|growth)\b", text, re.I)
    assert "o‘sdi" not in text and "pasaydi" not in text  # no growth claim without a prior period


# --- counts ------------------------------------------------------------------

async def test_empty_database_is_all_zero_and_safe(db_session, clean_tables):
    s = await _stats(db_session)
    assert (s.active_1, s.active_7, s.active_30, s.new_users_1, s.new_users_7, s.new_users_30) == (0,) * 6
    assert (s.links_today, s.links_total, s.messages_1, s.messages_7, s.messages_30) == (0,) * 5
    assert "Bugun 0 nafar faol foydalanuvchi" in summary_uz(s)
    assert render_stats_card(s)[:8] == b"\x89PNG\r\n\x1a\n"


async def test_new_users_today_7_and_30_days(db_session, clean_tables):
    await _user(db_session, 1, NOW)                                # today
    await _user(db_session, 2, NOW - timedelta(days=3))            # in 7 and 30
    await _user(db_session, 3, NOW - timedelta(days=20))           # in 30 only
    await _user(db_session, 4, NOW - timedelta(days=45))           # in none
    s = await _stats(db_session)
    assert (s.new_users_1, s.new_users_7, s.new_users_30) == (1, 2, 3)


async def test_dau_wau_mau_count_distinct_users_not_events(db_session, clean_tables):
    for uid in (1, 2, 3, 4):
        await _user(db_session, uid, NOW - timedelta(days=90))
    for name in ("inbox_opened", "message_opened", "link_created"):   # 3 events, same person
        await _event(db_session, name, 1)
    await _event(db_session, "inbox_opened", 2, NOW - timedelta(days=4))     # WAU + MAU
    await _event(db_session, "inbox_opened", 3, NOW - timedelta(days=15))    # MAU only
    await _event(db_session, "inbox_opened", 4, NOW - timedelta(days=60))    # none
    s = await _stats(db_session)
    assert (s.active_1, s.active_7, s.active_30) == (1, 2, 3)


async def test_a_user_created_long_ago_is_not_active_without_an_event(db_session, clean_tables):
    await _user(db_session, 1, NOW)   # a brand-new row alone is not "active"
    s = await _stats(db_session)
    assert s.new_users_1 == 1 and s.active_1 == 0


async def test_anonymous_sender_side_and_non_user_events_are_excluded(db_session, clean_tables):
    await _user(db_session, 1, NOW - timedelta(days=90))
    for name in ("sender_page_viewed", "message_started", "message_sent", "sender_cta_clicked", "link_clicked"):
        await _event(db_session, name, None)                 # anonymous, user_id NULL
    await _event(db_session, "message_received", 1)         # worker-written delivery, not a user action
    await _event(db_session, "send_rate_limited", 1)
    assert "message_received" not in ACTIVE_EVENTS and "send_rate_limited" not in ACTIVE_EVENTS
    s = await _stats(db_session)
    assert (s.active_1, s.active_7, s.active_30) == (0, 0, 0)
    await _event(db_session, "inbox_opened", 1)
    assert (await _stats(db_session)).active_1 == 1


async def test_links_today_and_all_time(db_session, clean_tables):
    for uid in (1, 2, 3):
        await _user(db_session, uid)
    await _link(db_session, 1, NOW)
    await _link(db_session, 2, NOW - timedelta(days=10), active=False)   # counted in the total, not today
    await _link(db_session, 3, NOW - timedelta(days=100))
    s = await _stats(db_session)
    assert (s.links_today, s.links_total) == (1, 3)


async def test_messages_today_7_and_30_days(db_session, clean_tables):
    await _user(db_session, 1)
    link = await _link(db_session, 1)
    for delta in (timedelta(0), timedelta(hours=2), timedelta(days=3), timedelta(days=20), timedelta(days=50)):
        await _message(db_session, link, NOW - delta)
    s = await _stats(db_session)
    assert (s.messages_1, s.messages_7, s.messages_30) == (2, 3, 4)


async def test_day_boundaries_use_the_application_timezone_not_utc(db_session, clean_tables):
    await _user(db_session, 1, DAY_START)              # exactly local midnight -> today
    await _user(db_session, 2, DAY_START - SECOND)     # 1s before local midnight -> yesterday (23:59:59 local)
    await _user(db_session, 3, DAY_START + timedelta(hours=23, minutes=59))   # last minute of today
    await _user(db_session, 4, DAY_START + timedelta(days=1))                 # local midnight tomorrow -> not today
    s = await _stats(db_session)
    assert s.new_users_1 == 2 and s.new_users_7 == 3
    assert s.today.isoformat() == "2026-09-21"
    assert local_today(datetime(2026, 9, 20, 18, 59, tzinfo=timezone.utc)).isoformat() == "2026-09-20"
    assert local_today(datetime(2026, 9, 20, 19, 0, tzinfo=timezone.utc)).isoformat() == "2026-09-21"


async def test_window_edges_are_today_plus_6_and_today_plus_29_local_days(db_session, clean_tables):
    d7 = DAY_START - timedelta(days=6)     # first instant of the 7-day window
    d30 = DAY_START - timedelta(days=29)   # first instant of the 30-day window
    await _user(db_session, 1, d7)
    await _user(db_session, 2, d7 - SECOND)
    await _user(db_session, 3, d30)
    await _user(db_session, 4, d30 - SECOND)
    s = await _stats(db_session)
    assert s.new_users_7 == 1 and s.new_users_30 == 3


# --- PNG ---------------------------------------------------------------------

async def test_png_is_generated_and_independent_of_any_personal_data(db_session, clean_tables):
    await _user(db_session, 4242424242, NOW)
    link = await _link(db_session, 4242424242)
    await _message(db_session, link)
    await _event(db_session, "inbox_opened", 4242424242)
    real = await _stats(db_session)
    png = render_stats_card(real)
    assert Image.open(io.BytesIO(png)).size == (1080, 1350)
    # The renderer takes only the aggregate numbers: identical numbers give identical pixels,
    # whoever the users are, and no id/body/fingerprint string can be in the file.
    assert render_stats_card(real) == png
    assert b"SECRETBODY" not in png and b"4242424242" not in png and b"ffffffff" not in png
    import inspect
    assert list(inspect.signature(render_stats_card).parameters) == ["s"]
