"""Inline keyboard builders for every bot screen."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from core.copy import t
from core.models import Message

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
    b.button(text=t("share_cta", lang), callback_data="link:share")
    b.button(text="📥 " + ("Qutim" if lang == "uz" else "Входящие"), callback_data="inbox:open")
    b.button(text="⚙️ " + ("Sozlamalar" if lang == "uz" else "Настройки"), callback_data="settings:open")
    b.adjust(1, 2)
    return b.as_markup()


def home_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📥 " + ("Qutim" if lang == "uz" else "Входящие"), callback_data="inbox:open")
    b.button(text="🔗 " + ("Havolam" if lang == "uz" else "Моя ссылка"), callback_data="link:show")
    b.button(text="⚙️ " + ("Sozlamalar" if lang == "uz" else "Настройки"), callback_data="settings:open")
    b.adjust(2, 1)
    return b.as_markup()


def inbox_keyboard(lang: str, messages: list[Message]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for m in messages:
        unread_marker = "🔵 " if m.opened_at is None else ""
        preview = (m.body or "").replace("\n", " ")[:40]
        if len(m.body or "") > 40:
            preview += "…"
        b.button(text=f"{unread_marker}{preview or '···'}", callback_data=f"msg:open:{m.id}")
    b.button(text=t("share_cta", lang), callback_data="link:share")
    b.adjust(1)
    return b.as_markup()


def message_detail_keyboard(lang: str, message_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("🗑 O'chirish" if lang == "uz" else "🗑 Удалить"), callback_data=f"msg:delete:{message_id}")
    b.button(text=("🚩 Shikoyat" if lang == "uz" else "🚩 Жалоба"), callback_data=f"msg:report:{message_id}")
    b.button(text=("🚫 Bloklash" if lang == "uz" else "🚫 Заблокировать"), callback_data=f"msg:block:{message_id}")
    b.button(text=("🖼 Karta sifatida" if lang == "uz" else "🖼 Как карточка"), callback_data=f"msg:card:{message_id}")
    b.button(text=t("welcome_cta", lang), callback_data="link:create")
    b.button(text=("⬅️ Qutim" if lang == "uz" else "⬅️ Входящие"), callback_data="inbox:open")
    b.adjust(2, 2, 1, 1)
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
    b.adjust(2, 2, 1)
    return b.as_markup()


def settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("Maxfiylik" if lang == "uz" else "Приватность"), callback_data="settings:privacy")
    b.button(text=("Xavfsizlik" if lang == "uz" else "Безопасность"), callback_data="settings:safety")
    b.button(text=("Yordam" if lang == "uz" else "Помощь"), callback_data="settings:help")
    b.button(text=("Havolani yangilash" if lang == "uz" else "Обновить ссылку"), callback_data="settings:regenerate")
    b.button(text=("⬅️ Bosh sahifa" if lang == "uz" else "⬅️ Главная"), callback_data="home:open")
    b.adjust(2, 2, 1)
    return b.as_markup()


def back_to_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("⬅️ Sozlamalar" if lang == "uz" else "⬅️ Настройки"), callback_data="settings:open")
    return b.as_markup()


def privacy_keyboard(lang: str, web_base_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=("To'liq matn" if lang == "uz" else "Полный текст"),
        url=f"{web_base_url.rstrip('/')}/privacy?lang={lang}",
    )
    b.button(text=("⬅️ Sozlamalar" if lang == "uz" else "⬅️ Настройки"), callback_data="settings:open")
    b.adjust(1)
    return b.as_markup()


def moderation_item_keyboard(action_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Dismiss", callback_data=f"mod:dismiss:{action_id}")
    b.button(text="Escalate", callback_data=f"mod:escalate:{action_id}")
    b.button(text="Disable link", callback_data=f"mod:disablelink:{action_id}")
    b.adjust(3)
    return b.as_markup()
