"""FastAPI app: the sender web experience + health check."""

import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis

from core.config import get_settings
from core.copy import t

from web.routes import health, legal, sender

logger = logging.getLogger("shivir.web")
_error_templates = Jinja2Templates(directory="web/templates")

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'"
    ),
    # Harmless if served over plain HTTP in dev — browsers only act on this
    # header when the response itself was already fetched over HTTPS.
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def _trusted_hosts(settings) -> list[str]:
    hostname = urlparse(settings.web_base_url).hostname or "localhost"
    # Trust the www-prefixed variant alongside whichever form WEB_BASE_URL
    # itself uses — both shivir.online and www.shivir.online resolve to this
    # server and are proxied identically (see infra/nginx.conf.example), but
    # WEB_BASE_URL only ever names one of them.
    if hostname.startswith("www."):
        hosts = [hostname, hostname[len("www.") :]]
    else:
        hosts = [hostname, f"www.{hostname}"]
    if not settings.is_production:
        # Dev convenience + the ASGI test client's default host.
        hosts += ["testserver", "localhost", "127.0.0.1"]
    return hosts


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.settings = settings
    yield
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    # Interactive API docs leak the exact shape of internal endpoints (e.g.
    # /s/{token}/track, the SendPayload schema) for no benefit — this app has
    # no public API consumers. Off in production; left on in dev for
    # convenience while building against it locally.
    docs_kwargs = (
        {"docs_url": None, "redoc_url": None, "openapi_url": None}
        if settings.is_production
        else {}
    )
    app = FastAPI(title="Shivir", lifespan=lifespan, **docs_kwargs)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts(settings))

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    app.include_router(health.router)
    app.include_router(legal.router)
    app.include_router(sender.router)

    @app.exception_handler(Exception)
    async def on_unhandled_exception(request: Request, exc: Exception):
        # Never leak stack traces / DB errors / internal identifiers to the
        # client — log the real cause server-side, show plain-language copy.
        logger.exception("Unhandled error on %s", request.url.path)
        if request.url.path.endswith(("/send", "/track")):
            return JSONResponse({"status": "error", "message": t("generic_error", "uz")}, status_code=500)
        return HTMLResponse(
            _error_templates.get_template("invalid.html").render(
                {"request": request, "lang": "uz", "message": t("generic_error", "uz")}
            ),
            status_code=500,
        )

    return app


app = create_app()
