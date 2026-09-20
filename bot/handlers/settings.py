"""Settings / Privacy / Safety / Help / link regeneration — screens 14-18."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.analytics import track
from core.config import Settings
from core.copy import t
from core.link_prompts import DEFAULT_KEY, is_valid_key
from core.models import User
from core.services.links import (
    build_sender_url,
    get_or_create_user,
    get_prompt_key,
    is_paused,
    regenerate_link,
    set_paused,
    set_prompt_key,
)

from bot.keyboards import (
    back_to_settings_keyboard,
    confirm_keyboard,
    link_ready_keyboard,
    privacy_keyboard,
    prompt_keyboard,
    settings_keyboard,
)

router = Router(name="settings")

_SETTINGS_LABELS = {"⚙️ Sozlamalar", "⚙️ Настройки"}

HELP_TEXT = {
    "uz": (
        "Shivir yordamida do'stlaringiz sizga anonim xabar yuborishi mumkin.\n\n"
        "Havolangizni ulashing, kelgan xabarlarni Qutida ko'ring. "
        "Har qanday muammoli xabarni shikoyat qiling yoki bloklang."
    ),
    "ru": (
        "С Shivir друзья могут отправлять вам анонимные сообщения.\n\n"
        "Поделитесь своей ссылкой и читайте входящие во «Входящих». "
        "Любое проблемное сообщение можно отметить жалобой или заблокировать отправителя."
    ),
}


def _settings_view(user: User) -> tuple[str, object]:
    title = "⚙️ Sozlamalar" if user.lang == "uz" else "⚙️ Настройки"
    paused = is_paused(user)
    if paused:
        title = f"{title}\n\n{t('settings_paused_line', user.lang)}"
    return title, settings_keyboard(user.lang, paused=paused)


@router.callback_query(F.data == "settings:open")
async def on_settings_open(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    title, markup = _settings_view(user)
    await callback.message.edit_text(title, reply_markup=markup)
    await callback.answer()


@router.message(F.text.in_(_SETTINGS_LABELS))
async def on_settings_open_reply_button(message: Message, session: AsyncSession) -> None:
    user = await get_or_create_user(session, message.from_user.id)
    title, markup = _settings_view(user)
    await message.answer(title, reply_markup=markup)


@router.callback_query(F.data == "settings:pause")
async def on_pause(callback: CallbackQuery, session: AsyncSession) -> None:
    await _set_pause(callback, session, paused=True)


@router.callback_query(F.data == "settings:resume")
async def on_resume(callback: CallbackQuery, session: AsyncSession) -> None:
    await _set_pause(callback, session, paused=False)


async def _set_pause(callback: CallbackQuery, session: AsyncSession, *, paused: bool) -> None:
    """Acts only on callback.from_user — there is no way to pause someone else's link."""
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)
    changed = await set_paused(session, user, paused)
    if changed:
        await track("link_paused" if paused else "link_resumed", user_id=tg_user_id)
    await callback.answer(t("pause_on_toast" if paused else "pause_off_toast", user.lang))
    if changed:
        title, markup = _settings_view(user)
        await callback.message.edit_text(title, reply_markup=markup)


@router.callback_query(F.data == "settings:prompt")
async def on_prompt_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(
        t("prompt_menu_title", user.lang), reply_markup=prompt_keyboard(user.lang, get_prompt_key(user))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("settings:promptset:"))
async def on_prompt_set(callback: CallbackQuery, session: AsyncSession) -> None:
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)
    key = callback.data.split(":", 2)[2]
    # Validation boundary: callback data is client-controlled, so only an
    # allow-listed preset (or "none") is ever stored.
    if key != DEFAULT_KEY and not is_valid_key(key):
        await callback.answer(t("generic_error", user.lang), show_alert=True)
        return
    changed = await set_prompt_key(session, user, key)
    if changed:
        await track("prompt_selected", user_id=tg_user_id, preset=key)
    await callback.answer(t("prompt_saved_toast", user.lang))
    if changed:
        await callback.message.edit_text(
            t("prompt_menu_title", user.lang), reply_markup=prompt_keyboard(user.lang, key)
        )


@router.callback_query(F.data == "settings:privacy")
async def on_privacy(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(
        t("privacy_summary", user.lang),
        reply_markup=privacy_keyboard(user.lang, settings.web_base_url),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:safety")
async def on_safety(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(
        t("safety_summary", user.lang), reply_markup=back_to_settings_keyboard(user.lang)
    )
    await callback.answer()


@router.callback_query(F.data == "settings:help")
async def on_help(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(
        HELP_TEXT.get(user.lang, HELP_TEXT["uz"]), reply_markup=back_to_settings_keyboard(user.lang)
    )
    await callback.answer()


@router.callback_query(F.data == "settings:regenerate")
async def on_regenerate_prompt(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await get_or_create_user(session, callback.from_user.id)
    prompt = (
        "Eski havola ishlamay qoladi, yangi havola yaratiladi. Davom etasizmi?"
        if user.lang == "uz"
        else "Старая ссылка перестанет работать, будет создана новая. Продолжить?"
    )
    await callback.message.edit_text(
        prompt, reply_markup=confirm_keyboard(user.lang, "settings:regenerateconfirm", "settings:open")
    )
    await callback.answer()


@router.callback_query(F.data == "settings:regenerateconfirm")
async def on_regenerate_confirm(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)
    link = await regenerate_link(session, tg_user_id, reason="user_initiated")
    await track("link_regenerated", user_id=tg_user_id, link_id=link.id, reason="user_initiated")

    url = build_sender_url(settings.web_base_url, link.token)
    text = f"{t('link_ready_title', user.lang)}\n\n`{url}`"
    if is_paused(user):
        text += f"\n\n{t('link_paused_notice', user.lang)}"
    await callback.message.edit_text(text, reply_markup=link_ready_keyboard(user.lang, url), parse_mode="Markdown")
    await track("link_ready_viewed", user_id=tg_user_id)
    await callback.answer()
