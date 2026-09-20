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
        "uz": (
            "Yuboruvchining shaxsi xabar oluvchiga hech qachon ko'rsatilmaydi. "
            "Suiiste'moldan himoyalanish uchun bazada IP-manzil emas, undan hisoblangan bir tomonlama "
            "xesh saqlanadi; veb-server jurnallarida IP-manzil qisqa muddat qolishi mumkin.\n\n"
            "Shivir o'zi xabar to'qimaydi: soxta xabarlar, soxta bildirishnomalar va "
            "yuboruvchi haqida soxta ishoralar yo'q."
        ),
        "ru": (
            "Личность отправителя никогда не показывается получателю. "
            "Для защиты от злоупотреблений в базе хранится не IP-адрес, а вычисленный из него "
            "односторонний хеш; в журналах веб-сервера IP-адрес может кратко сохраняться.\n\n"
            "Shivir сам не выдумывает сообщения: никаких фейковых сообщений, уведомлений "
            "и ложных подсказок о том, кто отправитель."
        ),
    },
    "safety_summary": {
        "uz": "Haqorat, tahdid yoki nomaqbul xabarlar taqiqlanadi.",
        "ru": "Оскорбления, угрозы и неприемлемый контент запрещены.",
    },
    "sender_reassurance": {
        "uz": "Bu odamga anonim xabar yuboring. Ular kim yozganini bilishmaydi.",
        "ru": "Отправьте анонимное сообщение этому человеку. Они не узнают, кто вы.",
    },
    "sender_hint": {
        "uz": "Bu odamga anonim xabar yuboring.",
        "ru": "Отправьте анонимное сообщение этому человеку.",
    },
    "sender_assurance": {
        "uz": "Ular kim yozganini bilishmaydi.",
        "ru": "Они не узнают, кто вы.",
    },
    "sender_paused": {
        "uz": "Bu havola hozircha xabar qabul qilmayapti.",
        "ru": "Эта ссылка сейчас не принимает сообщения.",
    },
    "sent_invite": {
        "uz": "Xohlasang, sen ham o'z havolangni yaratib, do'stlaringdan anonim xabar ola olasan.",
        "ru": "Если хочешь, создай свою ссылку и получай анонимные сообщения от друзей.",
    },
    "link_paused_notice": {
        "uz": "⏸ Havolangiz to'xtatilgan — yangi xabarlar kelmaydi. Sozlamalardan yoqishingiz mumkin.",
        "ru": "⏸ Ваша ссылка приостановлена — новые сообщения не приходят. Включить можно в настройках.",
    },
    "settings_paused_line": {"uz": "⏸ Havola to'xtatilgan", "ru": "⏸ Ссылка приостановлена"},
    "settings_prompt_btn": {"uz": "✏️ Havola matni", "ru": "✏️ Текст ссылки"},
    "settings_pause_btn": {"uz": "⏸ Havolani to'xtatish", "ru": "⏸ Приостановить ссылку"},
    "settings_resume_btn": {"uz": "▶️ Havolani yoqish", "ru": "▶️ Включить ссылку"},
    "pause_on_toast": {
        "uz": "Havola to'xtatildi. Yangi xabarlar qabul qilinmaydi.",
        "ru": "Ссылка приостановлена. Новые сообщения не принимаются.",
    },
    "pause_off_toast": {"uz": "Havola yoqildi.", "ru": "Ссылка снова включена."},
    "prompt_menu_title": {
        "uz": "Havolangiz sahifasida ko'rinadigan qisqa matnni tanlang:",
        "ru": "Выберите короткую строку, которую увидят на странице вашей ссылки:",
    },
    "prompt_saved_toast": {"uz": "Saqlandi.", "ru": "Сохранено."},
    "compose_label": {"uz": "Anonim xabaringiz", "ru": "Ваше анонимное сообщение"},
    "prompts_label": {
        "uz": "Xabarni boshlash uchun takliflar",
        "ru": "Подсказки, с чего начать",
    },
    "sending_label": {"uz": "Yuborilmoqda…", "ru": "Отправка…"},
    "sent_label": {"uz": "Yuborildi", "ru": "Отправлено"},
    "chars_max_hint": {"uz": "Ko‘pi bilan {n} ta belgi.", "ru": "Не более {n} символов."},
    "chars_left": {"uz": "{n} ta belgi qoldi.", "ru": "Осталось символов: {n}."},
    "chars_limit_reached": {
        "uz": "Belgilar chegarasiga yetdingiz.",
        "ru": "Достигнут предел символов.",
    },
    "privacy_link": {"uz": "Maxfiylik siyosati", "ru": "Политика конфиденциальности"},
    "compose_placeholder": {"uz": "Xabaringizni yozing...", "ru": "Напишите сообщение..."},
    "send_cta": {"uz": "Yuborish", "ru": "Отправить"},
    "send_success": {
        "uz": "Xabaringiz yuborildi ✅ Oluvchi kim yozganini bilmaydi.",
        "ru": "Сообщение отправлено ✅ Получатель не узнает, кто вы.",
    },
    "sent_title": {"uz": "Xabaringiz yuborildi", "ru": "Сообщение отправлено"},
    "sent_reassurance": {"uz": "Oluvchi kim yozganini bilmaydi.", "ru": "Получатель не узнает, кто вы."},
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
    "share_message": {
        "uz": "Menga anonim xabar yubor 👀",
        "ru": "Отправь мне анонимное сообщение 👀",
    },
    "main_menu_ready": {"uz": "Asosiy menyu tayyor 👇", "ru": "Главное меню готово 👇"},
    "back_button": {"uz": "◀️ Orqaga", "ru": "◀️ Назад"},
}


def t(key: str, lang: str) -> str:
    entry = COPY.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry["uz"]
