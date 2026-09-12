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
from core.services.links import build_sender_url, create_link, get_active_link_for_owner, get_or_create_user

from bot.keyboards import home_keyboard, language_keyboard, link_ready_keyboard, welcome_keyboard

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = message.from_user.id
    existing = await session.get(User, tg_user_id)
    is_returning = existing is not None

    payload = message.text.split(maxsplit=1)[1] if " " in (message.text or "") else None
    await track(
        "bot_started",
        user_id=tg_user_id,
        source="deep_link" if payload else "organic",
        is_returning=is_returning,
    )

    if is_returning:
        await _send_home(message, existing.lang)
        return

    detected = (message.from_user.language_code or "uz").lower()
    default_lang = "ru" if detected.startswith("ru") else "uz"
    await get_or_create_user(session, tg_user_id, lang=default_lang)
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

    link = await create_link(session, owner_user_id=tg_user_id)
    await track("link_created", user_id=tg_user_id, link_id=link.id)

    await _render_link_ready(callback.message, user.lang, settings, link.token, tg_user_id, edit=True)
    await callback.answer()


@router.callback_query(F.data == "link:show")
async def on_link_show(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)
    link = await get_active_link_for_owner(session, tg_user_id)
    if link is None:
        link = await create_link(session, owner_user_id=tg_user_id)
        await track("link_created", user_id=tg_user_id, link_id=link.id)

    await _render_link_ready(callback.message, user.lang, settings, link.token, tg_user_id, edit=True)
    await callback.answer()


@router.callback_query(F.data == "link:share")
async def on_link_share(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)
    link = await get_active_link_for_owner(session, tg_user_id)
    if link is None:
        link = await create_link(session, owner_user_id=tg_user_id)

    await track("link_shared", user_id=tg_user_id, link_id=link.id, channel="telegram")

    toast = (
        "Havolani nusxalash uchun yuqoridagi matnni bosing"
        if user.lang == "uz"
        else "Нажмите на ссылку выше, чтобы скопировать её"
    )
    await callback.answer(toast, show_alert=True)


@router.callback_query(F.data == "home:open")
async def on_home_open(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(_home_text(user.lang), reply_markup=home_keyboard(user.lang))
    await callback.answer()


def _home_text(lang: str) -> str:
    return "Bosh sahifa" if lang == "uz" else "Главная"


async def _send_home(message: Message, lang: str) -> None:
    await message.answer(_home_text(lang), reply_markup=home_keyboard(lang))


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
