import httpx
from httpx import ASGITransport


async def test_privacy_page_uz_default(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/privacy")

    assert resp.status_code == 200
    assert "Maxfiylik siyosati" in resp.text
    assert "shaxsi hech qachon" in resp.text  # never reveals sender identity, stated plainly


async def test_privacy_page_russian(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/privacy?lang=ru")

    assert resp.status_code == 200
    assert "Политика конфиденциальности" in resp.text


async def test_privacy_page_unknown_lang_falls_back_to_uz(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/privacy?lang=fr")

    assert "Maxfiylik siyosati" in resp.text
