"""A liveness-only /health (just "is the process up") would report healthy
even while Postgres or Redis is down — exactly the outage an uptime monitor
pointed at this endpoint (see infra/DEPLOYMENT.md §7) needs to catch. This
checks both, fast (a single SELECT 1 / PING each)."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_session

router = APIRouter()


@router.get("/health")
async def health(request: Request, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    checks = {"database": False, "redis": False}

    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    try:
        await request.app.state.redis.ping()
        checks["redis"] = True
    except Exception:
        pass

    healthy = all(checks.values())
    return JSONResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status_code=200 if healthy else 503,
    )
