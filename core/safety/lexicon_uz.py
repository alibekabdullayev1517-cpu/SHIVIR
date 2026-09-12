"""Uzbek (Latin + common Cyrillic spellings) abuse lexicon v1.

Rules-only, V1 scope. Not exhaustive by design — see core/safety/filter.py for
why keyword filtering is treated as a first-pass signal, not a verdict.
"""

HARASSMENT = [
    "ahmoq", "axmoq", "jinni", "tentak", "qotoq", "nusxa", "yaramas",
    "iflos", "svoloch", "loph", "harom", "sharmanda", "razil",
    "хароп", "ахмок", "жинни",
]

THREAT = [
    "o'ldiraman", "oldiraman", "öldiraman", "o'ldirib qo'yaman",
    "ursam", "urib tashlayman", "topib olaman", "hisobingni beraman",
    "qonimga tashna", "o'ch olaman", "seni tugataman", "yo'q qilaman",
    "убью", "прибью", "найду тебя", "пожалеешь",
]

SEXUAL = [
    "sex", "seks", "porno", "nagish", "yalang'och", "jinsiy aloqa",
    "порно", "секс", "голая", "голый",
]

SPAM_KEYWORDS = [
    "bitcoin", "krypto invest", "tez boy bo'l", "pul ishla",
    "подписывайся", "заработок", "крипта инвест",
]
