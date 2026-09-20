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
        "line": {"uz": "Menga istalgan savol bering 👀", "ru": "Задайте мне любой вопрос 👀"},
        "label": {"uz": "👀 Savol", "ru": "👀 Вопрос"},
    },
    "honest": {
        "line": {"uz": "Menga halol fikringizni ayting.", "ru": "Скажите мне честно, что думаете."},
        "label": {"uz": "💬 Halol fikr", "ru": "💬 Честно"},
    },
    "compliment": {
        "line": {
            "uz": "Yaxshi gap aytmoqchimisiz? Anonim yozing.",
            "ru": "Хотите сказать что-то хорошее? Напишите анонимно.",
        },
        "label": {"uz": "💌 Iliq so'z", "ru": "💌 Тёплые слова"},
    },
    "birthday": {
        "line": {
            "uz": "Tug'ilgan kunim 🎂 — anonim tilaklar yuboring.",
            "ru": "У меня день рождения 🎂 — оставьте анонимное поздравление.",
        },
        "label": {"uz": "🎂 Tug'ilgan kun", "ru": "🎂 День рождения"},
    },
    "advice": {
        "line": {
            "uz": "Maslahat kerak — anonim fikringizni yozing.",
            "ru": "Нужен совет — напишите анонимно, что думаете.",
        },
        "label": {"uz": "🧭 Maslahat", "ru": "🧭 Совет"},
    },
    "memory": {
        "line": {
            "uz": "Birga o'tgan bir xotirani yozing.",
            "ru": "Напишите воспоминание о времени, проведённом вместе.",
        },
        "label": {"uz": "📸 Xotira", "ru": "📸 Воспоминание"},
    },
}

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
