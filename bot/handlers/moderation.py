"""Human moderation queue, reviewed via bot commands (V1 has no separate admin
web dashboard — that's V2+ per the master plan's Founder Dashboard section).
Restricted to the ADMIN_TG_USER_IDS allowlist.
"""

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from cards.stats_render import render_stats_card
from core.services.moderation import apply_moderator_decision, moderation_queue
from core.services.stats import collect_stats, report_uz

from bot.keyboards import moderation_item_keyboard

router = Router(name="moderation")
logger = logging.getLogger(__name__)


def _is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("modqueue"))
async def cmd_modqueue(message: Message, session: AsyncSession, settings: Settings) -> None:
    if not _is_admin(message.from_user.id, settings):
        return  # silent — no confirmation that this command exists to non-admins

    items = await moderation_queue(session, limit=10)
    if not items:
        await message.answer("Moderation queue is empty.")
        return

    for item in items:
        text = (
            f"[{item.severity}] {item.action} — {item.target}\n"
            f"by {item.moderator} at {item.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        if item.reason:
            text += f"\n\nEvidence:\n{item.reason[:500]}"
        # parse_mode=None is deliberate: `reason` can hold a raw sender-supplied
        # message body (evidence snapshot). The bot's default parse mode is
        # HTML — without this override that untrusted text would be parsed as
        # markup in front of the moderator, e.g. crafted clickable links.
        await message.answer(text, reply_markup=moderation_item_keyboard(item.id), parse_mode=None)


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, settings: Settings) -> None:
    """Admin-only aggregate report: Uzbek text, then one PNG. Read-only — records
    no event, so using it never makes the admin look like an active user."""
    if not _is_admin(message.from_user.id, settings):
        return  # silent, exactly like /modqueue

    stats = await collect_stats(session)
    await message.answer(report_uz(stats), parse_mode=None)
    try:
        png = await asyncio.to_thread(render_stats_card, stats)
        await message.answer_photo(BufferedInputFile(png, filename="shivir-stats.png"))
    except Exception:
        logger.exception("Stats card failed")  # the text report has already been delivered


@router.callback_query(F.data.startswith("mod:"))
async def on_moderation_decision(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer()
        return

    _, decision_code, action_id_str = callback.data.split(":")
    decision_map = {"dismiss": "dismiss", "escalate": "escalate", "disablelink": "disable_link"}
    decision = decision_map.get(decision_code)
    if decision is None:
        await callback.answer()
        return

    result = await apply_moderator_decision(
        session, callback.from_user.id, int(action_id_str), decision
    )
    if result is None:
        await callback.answer("Not found.", show_alert=True)
        return

    # apply_moderator_decision() is idempotent: result.action/moderator reflect
    # whichever decision actually resolved this target first, which may not be
    # this tap (a double-tap, or another moderator acting first) — the message
    # is worded generically-correct for both cases rather than assuming "this
    # tap just resolved it".
    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ resolved: {result.action} by {result.moderator}",
        parse_mode=None,
    )
    await callback.answer()
