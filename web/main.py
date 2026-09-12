"""FastAPI app: the sender web experience + health check."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from redis.asyncio import Redis

from core.config import get_settings
from core.copy import t

from web.routes import health, legal, sender

logger = logging.getLogger("shivir.web")
_error_templates = Jinja2Templates(directory="web/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.settings = settings
    yield
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Shivir", lifespan=lifespan)
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
