"""Inbox, message detail, delete/report/block, and share-as-card."""

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from cards.render import render_variant_a
from core.analytics import track
from core.config import Settings
from core.copy import t
from core.services.links import build_sender_url, get_active_link_for_owner
from core.services.messages import (
    count_unread,
    get_inbox_messages,
    get_message_for_recipient,
    mark_opened,
)
from core.services.moderation import block_sender, delete_message, report_message
from core.services.links import get_or_create_user

from bot.keyboards import (
    confirm_keyboard,
    inbox_keyboard,
    message_detail_keyboard,
    report_reason_keyboard,
)

router = Router(name="inbox")

_INBOX_LABELS = {"📥 Qutim", "📥 Входящие"}


async def _inbox_view(session: AsyncSession, settings: Settings, tg_user_id: int) -> tuple[str, object]:
    user = await get_or_create_user(session, tg_user_id)
    messages = await get_inbox_messages(session, tg_user_id)
    unread = await count_unread(session, tg_user_id)
    active_link = await get_active_link_for_owner(session, tg_user_id)
    share_url = build_sender_url(settings.web_base_url, active_link.token) if active_link else None

    await track("inbox_opened", user_id=tg_user_id, unread_count=unread)

    if not messages:
        return t("inbox_empty", user.lang), inbox_keyboard(user.lang, [], share_url)
    title = "📥 Qutingiz" if user.lang == "uz" else "📥 Входящие"
    return title, inbox_keyboard(user.lang, messages, share_url)


async def _render_inbox(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    text, markup = await _inbox_view(session, settings, callback.from_user.id)
    await callback.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "inbox:open")
async def on_inbox_open(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await _render_inbox(callback, session, settings)
    await callback.answer()


@router.message(F.text.in_(_INBOX_LABELS))
async def on_inbox_open_reply_button(message: Message, session: AsyncSession, settings: Settings) -> None:
    text, markup = await _inbox_view(session, settings, message.from_user.id)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("msg:open:"))
async def on_message_open(callback: CallbackQuery, session: AsyncSession) -> None:
    message_id = int(callback.data.split(":")[2])
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)

    message = await get_message_for_recipient(session, message_id, tg_user_id)
    if message is None:
        await callback.answer(t("generic_error", user.lang), show_alert=True)
        return

    await mark_opened(session, message)
    await track("message_opened", user_id=tg_user_id, message_id=message.id)

    when = message.created_at.strftime("%Y-%m-%d %H:%M")
    # parse_mode=None is deliberate: message.body is untrusted sender input.
    # Rendering it through Markdown/HTML would let a sender inject clickable
    # links (phishing) or malformed markup that breaks the message view.
    await callback.message.edit_text(
        f"{message.body}\n\n{when}",
        reply_markup=message_detail_keyboard(user.lang, message.id),
        parse_mode=None,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("msg:delete:"))
async def on_delete_prompt(callback: CallbackQuery, session: AsyncSession) -> None:
    message_id = int(callback.data.split(":")[2])
    user = await get_or_create_user(session, callback.from_user.id)
    await callback.message.edit_text(
        t("delete_confirm_prompt", user.lang),
        reply_markup=confirm_keyboard(user.lang, f"msg:deleteconfirm:{message_id}", f"msg:open:{message_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("msg:deleteconfirm:"))
async def on_delete_confirm(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    message_id = int(callback.data.split(":")[2])
    tg_user_id = callback.from_user.id
    message = await get_message_for_recipient(session, message_id, tg_user_id)
    if message is not None:
        await delete_message(session, message)
        await track("message_deleted", user_id=tg_user_id, message_id=message_id)
    await _render_inbox(callback, session, settings)
    await callback.answer()


@router.callback_query(F.data.startswith("msg:block:"))
async def on_block_prompt(callback: CallbackQuery, session: AsyncSession) -> None:
    message_id = int(callback.data.split(":")[2])
    user = await get_or_create_user(session, callback.from_user.id)
    prompt = (
        "Bu yuboruvchini bloklaysizmi? U sizga boshqa xabar yubora olmaydi."
        if user.lang == "uz"
        else "Заблокировать этого отправителя? Он больше не сможет вам писать."
    )
    await callback.message.edit_text(
        prompt,
        reply_markup=confirm_keyboard(user.lang, f"msg:blockconfirm:{message_id}", f"msg:open:{message_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("msg:blockconfirm:"))
async def on_block_confirm(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    message_id = int(callback.data.split(":")[2])
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)
    message = await get_message_for_recipient(session, message_id, tg_user_id)
    if message is not None:
        await block_sender(session, tg_user_id, message.sender_fingerprint_hash)
        await track("sender_blocked", user_id=tg_user_id, message_id=message_id)
        await callback.answer(t("block_confirmation", user.lang), show_alert=True)
    await _render_inbox(callback, session, settings)


@router.callback_query(F.data.startswith("msg:report:"))
async def on_report_prompt(callback: CallbackQuery, session: AsyncSession) -> None:
    message_id = int(callback.data.split(":")[2])
    user = await get_or_create_user(session, callback.from_user.id)
    prompt = "Nima uchun shikoyat qilyapsiz?" if user.lang == "uz" else "Причина жалобы?"
    await callback.message.edit_text(prompt, reply_markup=report_reason_keyboard(message_id, user.lang))
    await callback.answer()


@router.callback_query(F.data.startswith("msg:reportreason:"))
async def on_report_reason(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    _, _, message_id_str, reason = callback.data.split(":")
    message_id = int(message_id_str)
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)

    message = await get_message_for_recipient(session, message_id, tg_user_id)
    if message is None:
        await callback.answer(t("generic_error", user.lang), show_alert=True)
        return

    await report_message(
        session, message, reason, auto_disable_threshold=settings.link_auto_disable_report_threshold
    )
    await track("report_created", user_id=tg_user_id, message_id=message_id, reason=reason)

    await callback.answer(t("report_confirmation", user.lang), show_alert=True)
    await _render_inbox(callback, session, settings)


@router.callback_query(F.data.startswith("msg:card:"))
async def on_share_card(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    message_id = int(callback.data.split(":")[2])
    tg_user_id = callback.from_user.id
    user = await get_or_create_user(session, tg_user_id)

    message = await get_message_for_recipient(session, message_id, tg_user_id)
    if message is None:
        await callback.answer(t("generic_error", user.lang), show_alert=True)
        return

    link = await get_active_link_for_owner(session, tg_user_id)
    cta_link = build_sender_url(settings.web_base_url, link.token) if link else settings.web_base_url

    png_bytes = render_variant_a(message.body, cta_link)
    caption = (
        "Kartani Instagram yoki Telegram'da ulashing!"
        if user.lang == "uz"
        else "Поделитесь карточкой в Instagram или Telegram!"
    )
    await callback.message.answer_photo(
        BufferedInputFile(png_bytes, filename="shivir-card.png"), caption=caption
    )
    await track("share_card_generated", user_id=tg_user_id, message_id=message_id)
    await callback.answer()
