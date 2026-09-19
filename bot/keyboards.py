"""Inline keyboard builders for every bot screen, plus the one persistent
ReplyKeyboardMarkup (main_reply_keyboard)."""

from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.copy import t
from core.models import Message
from core.services.links import build_telegram_share_url

REPORT_REASONS = [
    ("harassment", {"uz": "Haqorat", "ru": "Оскорбление"}),
    ("threat", {"uz": "Tahdid", "ru": "Угроза"}),
    ("sexual", {"uz": "Jinsiy kontent", "ru": "Сексуальный контент"}),
    ("spam", {"uz": "Spam", "ru": "Спам"}),
    ("other", {"uz": "Boshqa", "ru": "Другое"}),
]


def language_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="O'zbek", callback_data="lang:uz")
    b.button(text="Русский", callback_data="lang:ru")
    b.adjust(2)
    return b.as_markup()


def welcome_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("welcome_cta", lang), callback_data="link:create")
    return b.as_markup()


def link_ready_keyboard(lang: str, link_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    # A `url=` button is the only way to trigger Telegram's own native
    # share/forward picker client-side — it never fires a callback (a hard
    # Bot API limitation), so link_shared analytics cannot be tracked from
    # this button.
    b.button(text=t("share_cta", lang), url=build_telegram_share_url(link_url, t("share_message", lang)))
    b.adjust(1)
    return b.as_markup()


def main_reply_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """The 3 persistent main actions, shown below the chat input — replaces
    the old inline "home" screen. Sent once (see bot/handlers/start.py); it
    then stays attached to the chat across every future message/edit until
    explicitly replaced, so it must not be resent on every navigation."""
    inbox_label = "📥 Qutim" if lang == "uz" else "📥 Входящие"
    link_label = "🔗 Havolam" if lang == "uz" else "🔗 Моя ссылка"
    settings_label = "⚙️ Sozlamalar" if lang == "uz" else "⚙️ Настройки"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=inbox_label), KeyboardButton(text=link_label)],
            [KeyboardButton(text=settings_label)],
        ],
        resize_keyboard=True,
    )


def inbox_keyboard(lang: str, messages: list[Message], share_url: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for m in messages:
        unread_marker = "🔵 " if m.opened_at is None else ""
        preview = (m.body or "").replace("\n", " ")[:40]
        if len(m.body or "") > 40:
            preview += "…"
        b.button(text=f"{unread_marker}{preview or '···'}", callback_data=f"msg:open:{m.id}")
    if share_url:
        b.button(text=t("share_cta", lang), url=build_telegram_share_url(share_url, t("share_message", lang)))
    b.adjust(1)
    return b.as_markup()


def message_detail_keyboard(lang: str, message_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("🗑 O'chirish" if lang == "uz" else "🗑 Удалить"), callback_data=f"msg:delete:{message_id}")
    b.button(text=("🚩 Shikoyat" if lang == "uz" else "🚩 Жалоба"), callback_data=f"msg:report:{message_id}")
    b.button(text=("🚫 Bloklash" if lang == "uz" else "🚫 Заблокировать"), callback_data=f"msg:block:{message_id}")
    b.button(text=("🖼 Karta sifatida" if lang == "uz" else "🖼 Как карточка"), callback_data=f"msg:card:{message_id}")
    b.button(text=t("back_button", lang), callback_data="inbox:open")
    b.adjust(2, 2, 1)
    return b.as_markup()


def confirm_keyboard(lang: str, confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("Bekor qilish" if lang == "uz" else "Отмена"), callback_data=cancel_data)
    b.button(text=("Ha, davom etish" if lang == "uz" else "Да, продолжить"), callback_data=confirm_data)
    b.adjust(2)
    return b.as_markup()


def report_reason_keyboard(message_id: int, lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for code, labels in REPORT_REASONS:
        b.button(text=labels.get(lang, labels["uz"]), callback_data=f"msg:reportreason:{message_id}:{code}")
    b.button(text=t("back_button", lang), callback_data=f"msg:open:{message_id}")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("Maxfiylik" if lang == "uz" else "Приватность"), callback_data="settings:privacy")
    b.button(text=("Xavfsizlik" if lang == "uz" else "Безопасность"), callback_data="settings:safety")
    b.button(text=("Yordam" if lang == "uz" else "Помощь"), callback_data="settings:help")
    b.button(text=("Havolani yangilash" if lang == "uz" else "Обновить ссылку"), callback_data="settings:regenerate")
    b.button(text=t("back_button", lang), callback_data="home:open")
    b.adjust(2, 2, 1)
    return b.as_markup()


def back_to_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("back_button", lang), callback_data="settings:open")
    return b.as_markup()


def privacy_keyboard(lang: str, web_base_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=("To'liq matn" if lang == "uz" else "Полный текст"),
        url=f"{web_base_url.rstrip('/')}/privacy?lang={lang}",
    )
    b.button(text=t("back_button", lang), callback_data="settings:open")
    b.adjust(1)
    return b.as_markup()


def moderation_item_keyboard(action_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Dismiss", callback_data=f"mod:dismiss:{action_id}")
    b.button(text="Escalate", callback_data=f"mod:escalate:{action_id}")
    b.button(text="Disable link", callback_data=f"mod:disablelink:{action_id}")
    b.adjust(3)
    return b.as_markup()
