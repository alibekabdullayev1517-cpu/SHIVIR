"""Aggregate-only statistics for the admin /stats command (internal founder tool).

Everything here is a read-only COUNT over existing tables; nothing per-user ever
leaves the database, and nothing is written (no events, no rows).

"Active" is NOT "has a row in users". A user is active on a day when they did
something meaningful in the Telegram bot: an event in ACTIVE_EVENTS with their
own user_id. Deliberately excluded:
  - message_received: written by the notification worker when a message is
    delivered to someone, not something the user did;
  - every sender-side web event (link_clicked, sender_page_viewed,
    message_started, message_sent, ...): anonymous, user_id is NULL;
  - admin/moderation commands (/stats, /modqueue): they record no event at all.

"Today" is the calendar day in STATS_TIMEZONE (the app has no configured
timezone; SHIVIR is an Uzbekistan product, and Asia/Tashkent is UTC+5 with no
DST). Windows: today; today + 6 previous days; today + 29 previous days.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Event, Message, PublicLink, User

STATS_TIMEZONE = ZoneInfo("Asia/Tashkent")

# Events written from a Telegram user's own action in the bot, with user_id set.
ACTIVE_EVENTS = frozenset(
    {
        "bot_started",
        "onboarding_language_selected",
        "onboarding_completed",
        "link_created",
        "new_link_created",
        "link_ready_viewed",
        "link_regenerated",
        "link_paused",
        "link_resumed",
        "prompt_selected",
        "inbox_opened",
        "message_opened",
        "message_deleted",
        "sender_blocked",
        "report_created",
        "share_card_generated",
    }
)

_MONTHS = (
    "YANVAR", "FEVRAL", "MART", "APREL", "MAY", "IYUN",
    "IYUL", "AVGUST", "SENTABR", "OKTABR", "NOYABR", "DEKABR",
)


@dataclass(frozen=True)
class Stats:
    today: date
    active_1: int
    active_7: int
    active_30: int
    new_users_1: int
    new_users_7: int
    new_users_30: int
    links_today: int
    links_total: int
    messages_1: int
    messages_7: int
    messages_30: int


def _day_start_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=STATS_TIMEZONE).astimezone(timezone.utc)


def local_today(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(STATS_TIMEZONE).date()


async def collect_stats(session: AsyncSession, now: datetime | None = None) -> Stats:
    today = local_today(now)
    start_1 = _day_start_utc(today)
    start_7 = _day_start_utc(today - timedelta(days=6))
    start_30 = _day_start_utc(today - timedelta(days=29))
    end = _day_start_utc(today + timedelta(days=1))

    async def counts(created, where=(), distinct_col=None):
        """count (or count distinct) per window (1, 7, 30 days) in one aggregate query."""
        cols = []
        for start in (start_1, start_7, start_30):
            marker = distinct_col if distinct_col is not None else 1
            picked = case((created >= start, marker), else_=None)
            cols.append(func.count(distinct(picked)) if distinct_col is not None else func.count(picked))
        stmt = select(*cols).where(created >= start_30, created < end, *where)
        return tuple((await session.execute(stmt)).one())

    active = await counts(Event.created_at, where=(Event.user_id.is_not(None), Event.name.in_(ACTIVE_EVENTS)),
                          distinct_col=Event.user_id)
    users = await counts(User.created_at)
    messages = await counts(Message.created_at)
    links_today = (
        await session.execute(select(func.count(PublicLink.id)).where(PublicLink.created_at >= start_1, PublicLink.created_at < end))
    ).scalar_one()
    links_total = (await session.execute(select(func.count(PublicLink.id)))).scalar_one()

    return Stats(
        today=today,
        active_1=active[0], active_7=active[1], active_30=active[2],
        new_users_1=users[0], new_users_7=users[1], new_users_30=users[2],
        links_today=links_today, links_total=links_total,
        messages_1=messages[0], messages_7=messages[1], messages_30=messages[2],
    )


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def date_label(day: date) -> str:
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def summary_uz(s: Stats) -> str:
    """One factual sentence from today's numbers only — no growth claims (there is no prior-period comparison)."""
    return (
        f"Bugun {fmt(s.active_1)} nafar faol foydalanuvchi SHIVIR bilan o‘zaro aloqada bo‘ldi. "
        f"{fmt(s.new_users_1)} ta yangi foydalanuvchi qo‘shildi va {fmt(s.messages_1)} ta xabar yuborildi."
    )


def report_uz(s: Stats) -> str:
    return (
        "📊 SHIVIR — Bugungi statistika\n"
        "\n"
        "👥 FOYDALANUVCHILAR\n"
        f"Yangi foydalanuvchilar: {fmt(s.new_users_1)}\n"
        f"Faol foydalanuvchilar: {fmt(s.active_1)}\n"
        f"Faol foydalanuvchilar (7 kun): {fmt(s.active_7)}\n"
        f"Faol foydalanuvchilar (30 kun): {fmt(s.active_30)}\n"
        "\n"
        "🔗 HAVOLALAR\n"
        f"Bugun yaratilgan: {fmt(s.links_today)}\n"
        f"Jami: {fmt(s.links_total)}\n"
        "\n"
        "💬 XABARLAR\n"
        f"Bugun: {fmt(s.messages_1)}\n"
        f"7 kun: {fmt(s.messages_7)}\n"
        "\n"
        "📈 O‘SISH\n"
        f"Bugungi yangi foydalanuvchilar: +{fmt(s.new_users_1)}\n"
        f"Bugungi xabarlar: +{fmt(s.messages_1)}\n"
        "\n"
        "💡 XULOSA\n"
        f"{summary_uz(s)}"
    )
