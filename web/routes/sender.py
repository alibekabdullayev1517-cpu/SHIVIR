"""The sender web experience: landing+compose (merged, per spec — the compose
field must be visible immediately, no separate 'start' tap), send, and the
JSON API the page's own JS calls for send / message_started tracking.
"""

import random

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.analytics import track
from core.config import Settings, get_settings
from core.copy import t
from core.db import get_session
from core.models import User
from core.security import compute_fingerprint, generate_csrf_token, verify_csrf_token
from core.services.links import get_link_by_token
from core.services.messages import MAX_MESSAGE_LENGTH, SendStatus, send_message

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")

PROMPTS = {
    "uz": [
        "Sen haqingda...",
        "Eng yaxshi xotiram sen bilan...",
        "Aytolmagan bir gapim bor...",
        "Seni birinchi marta ko'rganimda...",
    ],
    "ru": [
        "О тебе...",
        "Лучшее воспоминание с тобой...",
        "Есть кое-что, что я не решался сказать...",
        "Когда я увидел тебя впервые...",
    ],
}


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def client_fingerprint(request: Request, settings: Settings) -> str:
    # SECURITY: take the LAST hop in X-Forwarded-For, not the first.
    # X-Forwarded-For is a client-supplied request header — anything in it
    # except the entry appended by our own (trusted, single-hop) Nginx proxy
    # is attacker-controlled. Taking the first entry let any sender forge a
    # fresh fingerprint on every request (`X-Forwarded-For: 1.2.3.4`), fully
    # defeating rate limiting and blocks. Nginx appends the real connecting
    # IP as the last item via `proxy_set_header X-Forwarded-For
    # $proxy_add_x_forwarded_for` (see infra/nginx.conf.example) — assumes
    # exactly one trusted proxy hop, which matches this deployment (uvicorn
    # bound to 127.0.0.1, only reachable through Nginx).
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[-1].strip() if forwarded else (request.client.host if request.client else "unknown")
    user_agent = request.headers.get("user-agent", "unknown")
    return compute_fingerprint(settings.secret_key, ip, user_agent)


@router.get("/s/{token}", response_class=HTMLResponse)
async def sender_landing(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    link = await get_link_by_token(session, token)
    await track("link_clicked", link_id=link.id if link else None, token=token if link is None else None)

    if link is None or not link.active:
        return templates.TemplateResponse(
            request, "invalid.html", {"lang": "uz", "message": t("link_invalid", "uz")}, status_code=404
        )

    owner = await session.get(User, link.owner_user_id)
    lang = owner.lang if owner else "uz"
    display_name = (owner.settings or {}).get("display_name") if owner else None

    csrf_token = generate_csrf_token(settings.secret_key, context=token)
    prompts = random.sample(PROMPTS.get(lang, PROMPTS["uz"]), k=min(3, len(PROMPTS.get(lang, PROMPTS["uz"]))))

    await track("sender_page_viewed", link_id=link.id)

    return templates.TemplateResponse(
        request,
        "sender_landing.html",
        {
            "lang": lang,
            "display_name": display_name,
            "token": token,
            "csrf_token": csrf_token,
            "prompts": prompts,
            "max_length": MAX_MESSAGE_LENGTH,
            "copy": {
                "reassurance": t("sender_reassurance", lang),
                "placeholder": t("compose_placeholder", lang),
                "send_cta": t("send_cta", lang),
                "success": t("send_success", lang),
                "success_secondary_cta": t("send_success_secondary_cta", lang),
                "rate_limited": t("rate_limited", lang),
                "generic_error": t("generic_error", lang),
                "abuse_prompt": t("abuse_warning_prompt", lang),
                "abuse_edit": t("abuse_warning_edit", lang),
                "abuse_continue": t("abuse_warning_continue", lang),
            },
            "bot_username": settings.bot_username,
        },
    )


class SendPayload(BaseModel):
    message: str = Field(min_length=0, max_length=MAX_MESSAGE_LENGTH + 1)
    csrf_token: str
    acknowledge_warning: bool = False


@router.post("/s/{token}/send")
async def sender_send(
    token: str,
    payload: SendPayload,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    if not verify_csrf_token(settings.secret_key, payload.csrf_token, context=token):
        return JSONResponse({"status": "error", "message": t("generic_error", "uz")}, status_code=403)

    link = await get_link_by_token(session, token)
    if link is None:
        return JSONResponse({"status": "invalid_link"}, status_code=404)

    owner = await session.get(User, link.owner_user_id)
    lang = owner.lang if owner else "uz"

    fingerprint = client_fingerprint(request, settings)
    result = await send_message(
        session,
        redis,
        settings,
        link_id=link.id,
        link_active=link.active,
        recipient_user_id=link.owner_user_id,
        body=payload.message,
        fingerprint_hash=fingerprint,
        acknowledge_warning=payload.acknowledge_warning,
    )

    if result.status == SendStatus.INVALID_LINK:
        return JSONResponse({"status": "invalid_link"}, status_code=404)

    if result.status in (SendStatus.EMPTY_MESSAGE, SendStatus.TOO_LONG):
        return JSONResponse({"status": "validation_error", "reason": result.status.value}, status_code=422)

    if result.status == SendStatus.RATE_LIMITED:
        await track("send_rate_limited", link_id=link.id, scope=result.rate_limit_scope)
        # 429, not the implicit 200: the frontend keys off the JSON `status`
        # field either way (see sender_landing.html), never response.status,
        # so this doesn't change client behavior — it just makes the
        # response semantically correct for any other consumer/monitoring.
        return JSONResponse(
            {"status": "rate_limited", "message": t("rate_limited", lang)}, status_code=429
        )

    if result.status == SendStatus.NEEDS_WARNING:
        await track("abuse_warning_shown", link_id=link.id, trigger_category=result.warning_category)
        return JSONResponse({"status": "needs_warning", "category": result.warning_category})

    if result.status == SendStatus.BLOCKED_SILENT:
        # Per spec: sender sees a normal success screen, nothing is delivered,
        # and nothing sender-identifying is written to analytics for this event.
        return JSONResponse({"status": "success", "message": t("send_success", lang)})

    # STORED
    await track("message_sent", link_id=link.id, char_count=len(payload.message))
    return JSONResponse({"status": "success", "message": t("send_success", lang)})


@router.post("/s/{token}/track")
async def sender_track_event(token: str, request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """The only client-triggered analytics beacon. Deliberately allow-lists a
    single event: message_started can only be observed client-side (first
    keystroke), and carries nothing sender-identifying."""
    try:
        body = await request.json()
    except Exception:
        # Malformed/empty/non-JSON body — treat as benign telemetry noise
        # (a network hiccup, a browser quirk, someone probing the endpoint),
        # not a server error. Same response as an unrecognized event name;
        # never a 500 for input this expected to be untrusted and low-stakes.
        return JSONResponse({"status": "ignored"})

    if not isinstance(body, dict) or body.get("name") != "message_started":
        return JSONResponse({"status": "ignored"})

    link = await get_link_by_token(session, token)
    if link is not None:
        await track("message_started", link_id=link.id)
    return JSONResponse({"status": "ok"})
