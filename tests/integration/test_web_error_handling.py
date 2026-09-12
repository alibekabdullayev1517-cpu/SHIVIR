"""When something downstream breaks (e.g. Redis is unreachable), the sender
must see plain-language copy, never a stack trace or bare 500 text."""

import httpx
from httpx import ASGITransport
from redis.asyncio import Redis

from core.models import User
from core.services.links import create_link


async def test_send_endpoint_degrades_gracefully_when_redis_is_down(db_session, clean_tables):
    from web.main import app

    db_session.add(User(tg_user_id=3001, lang="uz"))
    await db_session.commit()
    link = await create_link(db_session, owner_user_id=3001)

    # Point at a port nothing listens on, to force a real connection failure.
    app.state.redis = Redis.from_url("redis://127.0.0.1:1", socket_connect_timeout=1)

    # raise_app_exceptions=False: without it httpx's test transport re-raises the
    # exception instead of letting FastAPI's registered handler produce a
    # response, which is the opposite of what happens under real uvicorn.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        page = await client.get(f"/s/{link.token}")
        import re

        csrf = re.search(r'const csrfToken = "([^"]+)"', page.text).group(1)

        resp = await client.post(
            f"/s/{link.token}/send",
            json={"message": "salom", "csrf_token": csrf},
        )

    assert resp.status_code == 500
    body = resp.json()
    assert "Traceback" not in resp.text
    assert "ConnectionError" not in resp.text
    assert body["message"]  # plain-language copy, not empty
