"""Privacy policy — plain-language, not legal boilerplate, and literally true
about anonymity (never claims identity "can never be known even by us" — we
say plainly what's hashed and why, per the master plan's PRIVACY section)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web import assets, i18n

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")
assets.register(templates)
i18n.register(templates)

PARAGRAPHS = {
    "uz": [
        "Shivir — anonim xabar almashish xizmati. Ushbu sahifa nimalarni saqlashimizni "
        "va saqlamasligimizni ochiq tushuntiradi.",
        "Biz nimalarni saqlaymiz: xabar oluvchining Telegram identifikatori, ismi va tili, xabar matni "
        "(siz uni o'chirmaguningizcha), havola tokenlari, xabar yuborish vaqti va foydalanish statistikasi. "
        "Oluvchining harakatlari (masalan, qutini ochish) uning identifikatori bilan bog'lanadi; "
        "yuboruvchining harakatlari esa hech qanday Telegram hisobiga bog'lanmaydi.",
        "Suiiste'moldan himoyalanish uchun yuboruvchining IP-manzili va brauzeri asosida "
        "bir tomonlama xesh (hash) hisoblanadi va ma'lumotlar bazasida saqlanadi. Bu xeshdan asl "
        "IP-manzilni tiklab bo'lmaydi — u faqat spam/tahdidlarni cheklash va bloklash uchun ishlatiladi. "
        "Shu sababli bir xil qurilmadan kelgan xabarlar bir-biriga bog'lanishi mumkin.",
        "Biz saqlamaymiz: yuboruvchining Telegram identifikatori yoki ismi, aniq joylashuv, "
        "doimiy kuzatuv cookie'lari. Veb-server texnik jurnallarida yuboruvchining IP-manzili qisqa "
        "muddat (hozircha taxminan ikki hafta) saqlanadi va keyin o'chiriladi; xom IP-manzillarning "
        "uzoq muddatli jurnali yuritilmaydi. Shu vaqt oralig'ida xizmat administratori xabar vaqtini "
        "server jurnali bilan solishtirib, yuboruvchining IP-manzilini bilib olishi texnik jihatdan mumkin.",
        "Xabarni o'chirsangiz, uning matni ma'lumotlar bazasidan o'chiriladi; kunlik zaxira nusxalarda "
        "u yana taxminan ikki hafta saqlanib qolishi mumkin. Agar xabar shikoyat qilingan yoki xavfsizlik "
        "filtri uni jiddiy xavfli deb belgilagan bo'lsa, moderatsiya uchun nusxa saqlanadi; hozircha "
        "bunday nusxalar avtomatik o'chirilmaydi.",
        "Xabar yuborilganda ekranda tasdiq ko'rsatiladi. Agar oluvchi sizni bloklagan bo'lsa yoki xabar "
        "xavfsizlik qoidalariga zid deb topilsa, u oluvchiga yetkazilmasligi mumkin.",
        "Shivir o'zi xabar to'qimaydi: soxta xabarlar, soxta bildirishnomalar va yuboruvchi "
        "haqida soxta ishoralar yo'q.",
        "Yuboruvchining shaxsi hech qachon xabar oluvchiga ko'rsatilmaydi.",
    ],
    "ru": [
        "Shivir — сервис для анонимных сообщений. Эта страница честно объясняет, что мы "
        "храним, а что нет.",
        "Что мы храним: Telegram ID, имя и язык получателя, текст сообщения (пока вы его не удалите), "
        "токены ссылок, время отправки и статистику использования. Действия получателя (например, "
        "открытие входящих) связаны с его идентификатором; действия отправителя не связываются "
        "ни с одним аккаунтом Telegram.",
        "Для защиты от злоупотреблений на основе IP-адреса и браузера отправителя вычисляется "
        "односторонний хеш, который хранится в базе данных. Из этого хеша нельзя восстановить "
        "IP-адрес — он используется только для ограничения спама/угроз и блокировок. Поэтому "
        "сообщения с одного и того же устройства могут связываться между собой.",
        "Что мы не храним: Telegram ID или имя отправителя, точное местоположение, постоянные "
        "отслеживающие cookie. В технических журналах веб-сервера IP-адрес отправителя хранится "
        "недолго (сейчас около двух недель), затем удаляется; долгосрочный журнал сырых "
        "IP-адресов не ведётся. В этот период администратор сервиса технически может сопоставить время "
        "сообщения с журналом сервера и узнать IP-адрес отправителя.",
        "Если вы удаляете сообщение, его текст удаляется из базы данных; в ежедневных резервных "
        "копиях он может сохраняться ещё около двух недель. Если на сообщение подана жалоба или "
        "защитный фильтр отметил его как серьёзно опасное, для модерации сохраняется копия; сейчас "
        "такие копии автоматически не удаляются.",
        "После отправки вы видите подтверждение. Если получатель вас заблокировал или сообщение "
        "нарушает правила безопасности, оно может быть не доставлено.",
        "Shivir не выдумывает сообщения: никаких фейковых сообщений, уведомлений и ложных "
        "подсказок о том, кто отправитель.",
        "Личность отправителя никогда не показывается получателю.",
    ],
}

TITLES = {"uz": "Maxfiylik siyosati", "ru": "Политика конфиденциальности"}
BACK_LABELS = {"uz": "← Orqaga", "ru": "← Назад"}


def _structure(paragraphs: list[str]) -> list[dict]:
    """Presentation only — the wording above is untouched. First paragraph is
    the lead, last is the closing callout, and a short "Label:" opener
    ("Biz nimalarni saqlaymiz:") is split out so it can be set in bold."""
    blocks = []
    for i, text in enumerate(paragraphs):
        kind = "lead" if i == 0 else "note" if i == len(paragraphs) - 1 else "body"
        head, sep, rest = text.partition(":")
        if kind == "body" and sep and len(head) <= 40:
            blocks.append({"kind": kind, "lead_in": head + ":", "text": rest.strip()})
        else:
            blocks.append({"kind": kind, "lead_in": None, "text": text})
    return blocks


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request, lang: str | None = None, back: str | None = None) -> HTMLResponse:
    lang = i18n.resolve_lang(lang)
    back_path = i18n.safe_back(back)   # only ever a /s/<token> path — never an arbitrary URL
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "lang": lang,
            "title": TITLES[lang],
            "blocks": _structure(PARAGRAPHS[lang]),
            "back_url": f"{back_path}?lang={lang}" if back_path else None,
            "back_label": BACK_LABELS[lang],
        },
    )
