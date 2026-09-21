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
        "uz": "Nima deging kelyapti?",
        "ru": "Что хочется сказать?",
    },
    "sender_assurance": {
        "uz": "Oluvchi kim yozganini bilmaydi.",
        "ru": "Получатель не узнает, кто ты.",
    },
    "sender_paused": {
        "uz": "Bu havola hozircha xabar qabul qilmayapti.",
        "ru": "Эта ссылка сейчас не принимает сообщения.",
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
    "compose_label": {
        "uz": "Anonim xabar",
        "ru": "Анонимное сообщение",
    },
    "sending_label": {"uz": "Yuborilmoqda…", "ru": "Отправка…"},
    "sent_label": {"uz": "Yuborildi", "ru": "Отправлено"},
    "chars_max_hint": {"uz": "Ko‘pi bilan {n} ta belgi.", "ru": "Не более {n} символов."},
    "chars_left": {"uz": "{n} ta belgi qoldi.", "ru": "Осталось символов: {n}."},
    "chars_limit_reached": {
        "uz": "Belgilar chegarasiga yetding.",
        "ru": "Достигнут предел символов.",
    },
    "prompts_label": {
        "uz": "Xabarni boshlash uchun takliflar",
        "ru": "Подсказки, с чего начать",
    },
    "send_cta": {"uz": "Yuborish", "ru": "Отправить"},
    "privacy_link": {"uz": "Maxfiylik siyosati", "ru": "Политика конфиденциальности"},
    "compose_placeholder": {
        "uz": "Xabaringni yoz...",
        "ru": "Напиши сообщение...",
    },
    "sent_title": {
        "uz": "Xabaring yuborildi",
        "ru": "Сообщение отправлено",
    },
    "rate_limited": {
        "uz": "Juda tez-tez xabar yubording. Bir necha daqiqadan so'ng qayta urinib ko'r.",
        "ru": "Ты отправляешь сообщения слишком часто. Попробуй через несколько минут.",
    },
    "link_invalid": {"uz": "Bu havola faol emas.", "ru": "Эта ссылка не активна."},
    "abuse_warning_prompt": {
        "uz": "Bu xabar qoidalarga zid bo'lishi mumkin. Davom etamizmi?",
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
    "compose_label_named": {
        "uz": "{name} uchun anonim xabar",
        "ru": "Анонимное сообщение для {name}",
    },
    "send_success": {
        "uz": "Xabaring yuborildi ✅ Oluvchi kim yozganini bilmaydi.",
        "ru": "Сообщение отправлено ✅ Получатель не узнает, кто ты.",
    },
    "sent_reassurance": {
        "uz": "Oluvchi kim yozganini bilmaydi.",
        "ru": "Получатель не узнает, кто ты.",
    },
    "web_error": {
        "uz": "Nimadir xato ketdi. Qayta urinib ko'r.",
        "ru": "Что-то пошло не так. Попробуй ещё раз.",
    },
    "web_offline": {
        "uz": "Internetga ulanib bo'lmadi. Qayta urinib ko'r.",
        "ru": "Нет соединения. Попробуй ещё раз.",
    },
    "web_back": {
        "uz": "← Orqaga",
        "ru": "← Назад",
    },
    "lang_switch_label": {
        "uz": "Til",
        "ru": "Язык",
    },
    "sent_ask": {
        "uz": "Endi senga nima yozishsin? 👀",
        "ru": "А что написали бы тебе? 👀",
    },
    "reason_ask": {
        "uz": "💬 Savol",
        "ru": "💬 Вопрос",
    },
    "reason_compliment": {
        "uz": "💛 Iliq gap",
        "ru": "💛 Тёплые слова",
    },
    "reason_advice": {
        "uz": "💡 Maslahat",
        "ru": "💡 Совет",
    },
    "reason_funny": {
        "uz": "😄 Hazil",
        "ru": "😄 Шутка",
    },
    "reason_note": {
        "uz": "Yangi havolangda shu mavzu tanlangan bo'ladi.",
        "ru": "В твоей новой ссылке будет выбрана эта тема.",
    },
    "success_cta": {
        "uz": "Men ham SHIVIR ochaman",
        "ru": "Хочу свой SHIVIR",
    },
    "success_cta_hint": {
        "uz": "Telegram'da ochiladi",
        "ru": "Откроется в Telegram",
    },
}


def t(key: str, lang: str) -> str:
    entry = COPY.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry["uz"]
