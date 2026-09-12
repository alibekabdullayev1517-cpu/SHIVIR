"""UX writing system — Uzbek primary, Russian fallback (master plan §UX WRITING
SYSTEM). Centralized so no screen invents its own wording.
"""

COPY: dict[str, dict[str, str]] = {
    "start_greeting": {
        "uz": "Salom! Shivir — sizga do'stlaringizdan anonim xabarlar keladigan joy 👀",
        "ru": "Привет! Shivir — место, где друзья могут отправить тебе анонимное сообщение 👀",
    },
    "start_cta": {"uz": "Boshlash", "ru": "Начать"},
    "language_prompt": {"uz": "Tilni tanlang / Выберите язык", "ru": "Tilni tanlang / Выберите язык"},
    "welcome_body": {
        "uz": "Shaxsiy havolangizni yarating, uni ulashing — do'stlaringiz sizga anonim xabar yubora oladi.",
        "ru": "Создайте свою ссылку и поделитесь ею — друзья смогут присылать вам анонимные сообщения.",
    },
    "welcome_cta": {"uz": "Havola yaratish", "ru": "Создать ссылку"},
    "link_creating": {"uz": "Havolangiz tayyorlanmoqda...", "ru": "Готовим вашу ссылку..."},
    "link_ready_title": {
        "uz": "Tayyor! Endi bu havolani Instagram yoki Telegram'da ulashing.",
        "ru": "Готово! Поделитесь этой ссылкой в Instagram или Telegram.",
    },
    "share_cta": {"uz": "Ulashish", "ru": "Поделиться"},
    "copy_cta": {"uz": "Nusxalash", "ru": "Копировать"},
    "copied_confirmation": {"uz": "Nusxalandi ✅", "ru": "Скопировано ✅"},
    "inbox_empty": {
        "uz": "Hozircha xabar yo'q. Havolangizni ulashing!",
        "ru": "Пока нет сообщений. Поделитесь ссылкой!",
    },
    "report_confirmation": {"uz": "Bu xabar shikoyat qilindi", "ru": "Жалоба на сообщение отправлена"},
    "block_confirmation": {"uz": "Bu yuboruvchi bloklandi", "ru": "Отправитель заблокирован"},
    "delete_confirm_prompt": {
        "uz": "Bu xabar butunlay o'chiriladi",
        "ru": "Это сообщение будет удалено навсегда",
    },
    "privacy_summary": {
        "uz": "Biz yuboruvchining shaxsini saqlamaymiz va hech qachon oshkor qilmaymiz.",
        "ru": "Мы не сохраняем и никогда не раскрываем личность отправителя.",
    },
    "safety_summary": {
        "uz": "Haqorat, tahdid yoki nomaqbul xabarlar taqiqlanadi.",
        "ru": "Оскорбления, угрозы и неприемлемый контент запрещены.",
    },
    "sender_reassurance": {
        "uz": "Bu odamga anonim xabar yuboring. Ular kim yozganini bilishmaydi.",
        "ru": "Отправьте анонимное сообщение этому человеку. Они не узнают, кто вы.",
    },
    "compose_placeholder": {"uz": "Xabaringizni yozing...", "ru": "Напишите сообщение..."},
    "send_cta": {"uz": "Yuborish", "ru": "Отправить"},
    "send_success": {
        "uz": "Xabaringiz yuborildi ✅ Anonimligingiz saqlanadi.",
        "ru": "Сообщение отправлено ✅ Ваша анонимность сохранена.",
    },
    "send_success_secondary_cta": {
        "uz": "O'zingizning Shivir havolangizni yarating",
        "ru": "Создайте свою ссылку Shivir",
    },
    "rate_limited": {
        "uz": "Juda tez-tez xabar yubordingiz. Bir necha daqiqadan so'ng qayta urinib ko'ring.",
        "ru": "Вы отправляете сообщения слишком часто. Попробуйте через несколько минут.",
    },
    "link_invalid": {"uz": "Bu havola faol emas.", "ru": "Эта ссылка не активна."},
    "abuse_warning_prompt": {
        "uz": "Bu xabar qoidalarga zid bo'lishi mumkin. Davom etasizmi?",
        "ru": "Это сообщение может нарушать правила. Продолжить?",
    },
    "abuse_warning_edit": {"uz": "Tahrirlash", "ru": "Изменить"},
    "abuse_warning_continue": {"uz": "Baribir yuborish", "ru": "Всё равно отправить"},
    "generic_error": {
        "uz": "Nimadir xato ketdi. Qayta urinib ko'ring.",
        "ru": "Что-то пошло не так. Попробуйте снова.",
    },
    "new_message_notification": {
        "uz": "Sizga yangi Shivir xabari keldi 👀",
        "ru": "Вам пришло новое сообщение Shivir 👀",
    },
    "ads_disclosure": {"uz": "Bu — reklama", "ru": "Это реклама"},
}


def t(key: str, lang: str) -> str:
    entry = COPY.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry["uz"]
