"""Privacy policy — plain-language, not legal boilerplate, and literally true
about anonymity (never claims identity "can never be known even by us" — we
say plainly what's hashed and why, per the master plan's PRIVACY section)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

PARAGRAPHS = {
    "uz": [
        "Shivir — anonim xabar almashish xizmati. Ushbu sahifa nimalarni saqlashimizni "
        "va saqlamasligimizni ochiq tushuntiradi.",
        "Biz nimalarni saqlaymiz: xabar oluvchining Telegram identifikatori, xabar matni "
        "(siz uni o'chirmaguningizcha), havola tokenlari, xabar yuborish vaqti va umumiy "
        "(shaxsga bog'liq bo'lmagan) statistika.",
        "Suiiste'moldan himoyalanish uchun yuboruvchining IP-manzili va brauzeri asosida "
        "bir tomonlama xesh (hash) hisoblanadi. Bu xesh asl IP-manzilga qaytarib bo'lmaydi — "
        "u faqat spam/tahdidlarni cheklash va bloklashni ishlatish uchun ishlatiladi.",
        "Biz saqlamaymiz: yuboruvchining Telegram identifikatori yoki ismi, aniq joylashuv, "
        "doimiy kuzatuv cookie'lari, yoki xom IP-manzillarning uzoq muddatli jurnali.",
        "Xabarni o'chirsangiz, uning matni butunlay o'chiriladi. Agar xabar shikoyat qilingan "
        "bo'lsa, faqat shikoyat vaqtidagi nusxa moderatsiya uchun saqlanadi — bu ham faqat "
        "zarur muddatga.",
        "Yuboruvchining shaxsi hech qachon xabar oluvchiga ko'rsatilmaydi.",
    ],
    "ru": [
        "Shivir — сервис для анонимных сообщений. Эта страница честно объясняет, что мы "
        "храним, а что нет.",
        "Что мы храним: Telegram ID получателя, текст сообщения (пока вы его не удалите), "
        "токены ссылок, время отправки и агрегированную (обезличенную) статистику.",
        "Для защиты от злоупотреблений IP-адрес и браузер отправителя хешируются "
        "односторонним способом. Этот хеш нельзя обратить обратно в IP-адрес — он "
        "используется только для ограничения спama и блокировок.",
        "Что мы не храним: Telegram ID или имя отправителя, точное местоположение, "
        "постоянные отслеживающие cookie, длительные журналы сырых IP-адресов.",
        "Если вы удаляете сообщение, его текст удаляется полностью. Если на сообщение "
        "была подана жалоба, копия на момент жалобы сохраняется только для модерации — "
        "и только на необходимый срок.",
        "Личность отправителя никогда не показывается получателю.",
    ],
}

TITLES = {"uz": "Maxfiylik siyosati", "ru": "Политика конфиденциальности"}


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_policy(request: Request, lang: str = "uz") -> HTMLResponse:
    lang = lang if lang in PARAGRAPHS else "uz"
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {"lang": lang, "title": TITLES[lang], "paragraphs": PARAGRAPHS[lang]},
    )
