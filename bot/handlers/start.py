"""Start / language / welcome / link-creation — screens 1-6 of the master plan.

Note on returning users: the spec's screen-1 table has one ambiguous line
("Exit: Language (first-time) or Welcome (returning)") that reads inconsistently
with its own more specific acceptance line ("skip language/welcome for returning
users"). We follow the more specific/actionable line: a returning user's /start
goes straight to Home, not back through Welcome.
"""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.analytics import track
from core.config import Settings
from core.copy import t
from core.models import User
from core.services.links import (
    build_sender_url,
    create_link,
    get_active_link_for_owner,
    get_or_create_user,
    has_any_link,
    set_display_name,
)

from bot.keyboards import language_keyboard, link_ready_keyboard, main_reply_keyboard, welcome_keyboard

_LINK_LABELS = {"🔗 Havolam", "🔗 Моя ссылка"}

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = message.from_user.id
    existing = await session.get(User, tg_user_id)
    is_returning = existing is not None
    payload = message.text.split(maxsplit=1)[1] if " " in (message.text or "") else None

    # track() opens its own independent session/transaction (see
    # core/analytics.py) — it must never run before the user row it
    # references is committed, or Postgres rejects the insert (events.user_id
    # is a real FK to users.tg_user_id). For a first-time user that row
    # doesn't exist until get_or_create_user() below creates it, so track()
    # has to happen after, not before, in that branch.
    if is_returning:
        await set_display_name(session, existing, message.from_user.first_name)
        await track(
            "bot_started",
            user_id=tg_user_id,
            source="deep_link" if payload else "organic",
            is_returning=is_returning,
        )
        await _send_home(message, existing.lang)
        return

    detected = (message.from_user.language_code or "uz").lower()
    default_lang = "ru" if detected.startswith("ru") else "uz"
    user = await get_or_create_user(session, tg_user_id, lang=default_lang)
    await set_display_name(session, user, message.from_user.first_name)
    await track(
        "bot_started",
        user_id=tg_user_id,
        source="deep_link" if payload else "organic",
        is_returning=is_returning,
    )
    await message.answer(
        "Tilni tanlang / Выберите язык", reply_markup=language_keyboard()
    )


@router.callback_query(F.data.startswith("lang:"))
async def on_language_selected(callback: CallbackQuery, session: AsyncSession) -> None:
    lang = callback.data.split(":", 1)[1]
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id, lang=lang)
    user.lang = lang
    await session.commit()

    await track("onboarding_language_selected", user_id=tg_user_id, lang=lang)

    await callback.message.edit_text(t("welcome_body", lang), reply_markup=welcome_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data == "link:create")
async def on_create_link(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)

    await track("onboarding_completed", user_id=tg_user_id)

    is_first_ever_link = not await has_any_link(session, tg_user_id)
    link = await create_link(session, owner_user_id=tg_user_id)
    await track("link_created", user_id=tg_user_id, link_id=link.id)
    if is_first_ever_link:
        # The viral-loop signal: someone who discovered Shivir (via a share,
        # the meme channel, etc.) and created their first-ever link.
        await track("new_link_created", user_id=tg_user_id, link_id=link.id)

    await _render_link_ready(callback.message, user.lang, settings, link.token, tg_user_id, edit=True)
    if is_first_ever_link:
        # ReplyKeyboardMarkup can only be attached via a NEW message, never
        # via editMessageText (which _render_link_ready used above) — this
        # is the one point every brand-new user is guaranteed to pass
        # through exactly once, so it's the natural place to attach it.
        # Returning users already have it from _send_home on /start.
        await callback.message.answer(t("main_menu_ready", user.lang), reply_markup=main_reply_keyboard(user.lang))
    await callback.answer()


async def _show_my_link(session: AsyncSession, tg_user_id: int) -> tuple[str, str]:
    user = await get_or_create_user(session, tg_user_id)
    link = await get_active_link_for_owner(session, tg_user_id)
    if link is None:
        link = await create_link(session, owner_user_id=tg_user_id)
        await track("link_created", user_id=tg_user_id, link_id=link.id)
    return user.lang, link.token


@router.callback_query(F.data == "link:show")
async def on_link_show(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = callback.from_user.id
    lang, token = await _show_my_link(session, tg_user_id)
    await _render_link_ready(callback.message, lang, settings, token, tg_user_id, edit=True)
    await callback.answer()


@router.message(F.text.in_(_LINK_LABELS))
async def on_link_show_reply_button(message: Message, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = message.from_user.id
    lang, token = await _show_my_link(session, tg_user_id)
    await _render_link_ready(message, lang, settings, token, tg_user_id, edit=False)


@router.callback_query(F.data == "home:open")
async def on_home_open(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    # No inline keyboard needed here — the 3 main actions live on the
    # persistent reply keyboard (main_reply_keyboard), already attached by
    # this point for every user who can reach this screen.
    await callback.message.edit_text(_home_text(user.lang), reply_markup=None)
    await callback.answer()


def _home_text(lang: str) -> str:
    return "Bosh sahifa" if lang == "uz" else "Главная"


async def _send_home(message: Message, lang: str) -> None:
    await message.answer(_home_text(lang), reply_markup=main_reply_keyboard(lang))


async def _render_link_ready(
    message: Message, lang: str, settings: Settings, token: str, owner_user_id: int, *, edit: bool
) -> None:
    url = build_sender_url(settings.web_base_url, token)
    text = f"{t('link_ready_title', lang)}\n\n`{url}`"
    markup = link_ready_keyboard(lang, url)
    if edit:
        await message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")
    await track("link_ready_viewed", user_id=owner_user_id)
