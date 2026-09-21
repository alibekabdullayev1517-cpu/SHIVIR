"""Owner-selectable line shown to senders on the personal link page.

Presets only, on purpose: the owner picks one of a few fixed, localized lines —
they never type free text. That means nothing user-authored is ever rendered on
a public page (no HTML/JS injection, no phishing text, no abusive prompt, no
moderation queue for prompts), and no conversation state is needed in the bot.

The chosen key lives in `users.settings["prompt"]` (a JSON column that already
holds `display_name`), so this needs no schema migration. An unknown or stale
key is ignored and the default line is shown.
"""

DEFAULT_KEY = "none"

# key -> (line shown to the sender, short button label in the bot), per language.
PRESETS: dict[str, dict[str, dict[str, str]]] = {
    "ask": {
        "line": {"uz": "Menga istalgan savol ber 👀", "ru": "Задай мне любой вопрос 👀"},
        "label": {"uz": "👀 Savol", "ru": "👀 Вопрос"},
    },
    "honest": {
        "line": {"uz": "Menga halol fikringni ayt.", "ru": "Скажи мне честно, что думаешь."},
        "label": {"uz": "💬 Halol fikr", "ru": "💬 Честно"},
    },
    "compliment": {
        "line": {
            "uz": "Yaxshi gap aytmoqchimisan? Anonim yoz.",
            "ru": "Хочешь сказать что-то хорошее? Напиши анонимно.",
        },
        "label": {"uz": "💌 Iliq so'z", "ru": "💌 Тёплые слова"},
    },
    "birthday": {
        "line": {
            "uz": "Tug'ilgan kunim 🎂 — anonim tilak yubor.",
            "ru": "У меня день рождения 🎂 — оставь анонимное поздравление.",
        },
        "label": {"uz": "🎂 Tug'ilgan kun", "ru": "🎂 День рождения"},
    },
    "advice": {
        "line": {
            "uz": "Maslahat kerak — anonim fikringni yoz.",
            "ru": "Нужен совет — напиши анонимно, что думаешь.",
        },
        "label": {"uz": "🧭 Maslahat", "ru": "🧭 Совет"},
    },
    "memory": {
        "line": {
            "uz": "Birga o'tgan bir xotirani yoz.",
            "ru": "Напиши воспоминание о времени, проведённом вместе.",
        },
        "label": {"uz": "📸 Xotira", "ru": "📸 Воспоминание"},
    },
    "funny": {
        "line": {
            "uz": "Meni kuldiradigan bir gap yoz 😄",
            "ru": "Рассмеши меня — напиши что-нибудь весёлое 😄",
        },
        "label": {"uz": "😄 Hazil", "ru": "😄 Шутка"},
    },
}

# The four choices offered on the sender's post-send screen. Each is a real
# preset above: the choice travels in the Telegram deep link (`?start=r_<key>`)
# and, for a brand-new account only, becomes the line on their first link.
SENDER_REASON_KEYS: tuple[str, ...] = ("ask", "compliment", "advice", "funny")
REASON_START_PREFIX = "r_"

PRESET_KEYS: tuple[str, ...] = tuple(PRESETS)
DEFAULT_LABEL = {"uz": "Standart", "ru": "Стандартная"}


def is_valid_key(key: object) -> bool:
    return isinstance(key, str) and key in PRESETS


def line_for(key: object, lang: str) -> str | None:
    """The sender-facing line for a preset, or None for default/unknown keys."""
    if not is_valid_key(key):
        return None
    lines = PRESETS[key]["line"]
    return lines.get(lang) or lines["uz"]


def label_for(key: str, lang: str) -> str:
    labels = PRESETS[key]["label"]
    return labels.get(lang) or labels["uz"]
