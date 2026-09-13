"""/health must actually verify its dependencies, not just that the process
is running — a pure liveness check would report healthy through a Postgres
or Redis outage, defeating the uptime monitor pointed at it (see
infra/DEPLOYMENT.md §7)."""

import httpx
from httpx import ASGITransport
from redis.asyncio import Redis


async def test_health_reports_degraded_when_redis_is_unreachable():
    from web.main import app

    app.state.redis = Redis.from_url("redis://127.0.0.1:1", socket_connect_timeout=1)

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] is False


async def test_health_ok_when_dependencies_reachable(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": True, "redis": True}
