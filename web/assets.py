"""Cache-busting for /static assets.

nginx serves /static/ with a 7-day max-age (infra/nginx.conf.example), so a
browser that already has /static/style.css keeps using that copy even after a
redesign ships — new markup then renders against old CSS. Appending the file's
mtime as `?v=` gives every changed stylesheet a new URL, so it is refetched
immediately while unchanged files stay cached for the full week.
"""

from pathlib import Path

_STATIC = Path(__file__).parent / "static"


def static_version(name: str = "style.css") -> str:
    try:
        return str(int((_STATIC / name).stat().st_mtime))
    except OSError:
        return "0"


def register(templates) -> None:
    """Expose {{ asset_v('style.css') }} to a Jinja2Templates instance."""
    templates.env.globals["asset_v"] = static_version
