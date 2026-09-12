"""V1 abuse filter: keyword lexicon + simple heuristics.

Rules-only by design (per the master plan's AI Moderation Roadmap: V1 is
rules-only; AI classification is V2+). This is deliberately treated as a
first-pass *signal*, not a verdict — false negatives are expected and are why
report/block/human-moderation-queue exist as the real backstop.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from core.safety import lexicon_ru, lexicon_uz

_URL_RE = re.compile(r"https?://|www\.|t\.me/|instagram\.com/", re.IGNORECASE)
_PHONE_RE = re.compile(r"(\+?\d[\s-]?){7,}")
_REPEATED_CHAR_RE = re.compile(r"(.)\1{6,}")


class Category(str, Enum):
    HARASSMENT = "harassment"
    THREAT = "threat"
    SEXUAL = "sexual"
    SPAM = "spam"


class Severity(str, Enum):
    NONE = "none"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


_WEIGHTS = {
    Category.SPAM: 1,
    Category.HARASSMENT: 2,
    Category.SEXUAL: 3,
    Category.THREAT: 4,
}

# A score >= this triggers the pre-send abuse-warning interstitial.
WARN_THRESHOLD = 2
# A score >= this is treated as L3 (threats/sexual): auto-removed from the
# recipient's inbox pending human review, per the SAFETY section.
L3_THRESHOLD = 3


@dataclass
class FilterResult:
    score: int = 0
    categories: set[Category] = field(default_factory=set)

    @property
    def should_warn(self) -> bool:
        return self.score >= WARN_THRESHOLD

    @property
    def severity(self) -> Severity:
        if Category.THREAT in self.categories or Category.SEXUAL in self.categories:
            if self.score >= L3_THRESHOLD:
                return Severity.L3
        if Category.HARASSMENT in self.categories:
            return Severity.L2
        if Category.SPAM in self.categories:
            return Severity.L1
        return Severity.NONE

    @property
    def top_category(self) -> Category | None:
        for cat in (Category.THREAT, Category.SEXUAL, Category.HARASSMENT, Category.SPAM):
            if cat in self.categories:
                return cat
        return None


def _contains_any(text_lower: str, words: list[str]) -> bool:
    return any(word in text_lower for word in words)


def analyze(text: str) -> FilterResult:
    result = FilterResult()
    text_lower = text.lower()

    lexicons = [
        (Category.HARASSMENT, lexicon_uz.HARASSMENT + lexicon_ru.HARASSMENT),
        (Category.THREAT, lexicon_uz.THREAT + lexicon_ru.THREAT),
        (Category.SEXUAL, lexicon_uz.SEXUAL + lexicon_ru.SEXUAL),
        (Category.SPAM, lexicon_uz.SPAM_KEYWORDS + lexicon_ru.SPAM_KEYWORDS),
    ]
    for category, words in lexicons:
        if _contains_any(text_lower, words):
            result.categories.add(category)
            result.score += _WEIGHTS[category]

    # Heuristics (spam-shaped content regardless of keyword match).
    url_hits = len(_URL_RE.findall(text))
    if url_hits >= 2:
        result.categories.add(Category.SPAM)
        result.score += 1
    if _PHONE_RE.search(text):
        result.categories.add(Category.SPAM)
        result.score += 1
    if _REPEATED_CHAR_RE.search(text):
        result.categories.add(Category.SPAM)
        result.score += 1
    if len(text) > 20:
        letters = [c for c in text if c.isalpha()]
        if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.8:
            result.categories.add(Category.SPAM)
            result.score += 1

    return result
