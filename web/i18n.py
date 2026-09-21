"""Language for the public web pages.

Copy lives in core.copy (the one localization table the bot also uses). This
module only decides *which* language a request gets and builds the UZ | RU
switch links:

  1. `?lang=uz|ru` in the URL wins — it is how the choice survives page changes
     (sender -> privacy -> back), with no cookie and no stored state;
  2. otherwise the link owner's language (the previous behaviour);
  3. otherwise Uzbek.
"""

import re
from urllib.parse import urlencode

from fastapi import Request

from core.copy import t

SUPPORTED = ("uz", "ru")
DEFAULT = "uz"

# A same-site path back to a sender page. Anything else is dropped, so `back`
# can never be used as an open redirect.
_BACK_RE = re.compile(r"^/s/[A-Za-z0-9_-]{1,64}$")


def resolve_lang(requested: str | None, fallback: str | None = None) -> str:
    for candidate in (requested, fallback):
        if candidate in SUPPORTED:
            return candidate
    return DEFAULT


def safe_back(path: str | None) -> str | None:
    return path if path and _BACK_RE.fullmatch(path) else None


def lang_links(request: Request) -> dict[str, str]:
    """Same page, other language: path + existing query with `lang` replaced."""
    params = [
        (k, v)
        for k, v in request.query_params.multi_items()
        if k != "lang" and (k != "back" or safe_back(v))   # never echo an arbitrary `back` into a link
    ]
    return {code: f"{request.url.path}?{urlencode([('lang', code), *params])}" for code in SUPPORTED}


def register(templates) -> None:
    templates.env.globals["lang_links"] = lang_links
    templates.env.globals["t"] = t   # {{ t('key', lang) }} for chrome shared by every page
