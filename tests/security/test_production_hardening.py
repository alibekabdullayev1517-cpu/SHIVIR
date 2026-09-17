"""Regression tests for production-hardening findings: API docs disclosure,
missing security headers, and Host-header trust."""

import httpx
from httpx import ASGITransport


def test_docs_endpoints_disabled_when_env_is_production(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("WEB_BASE_URL", "https://shivir.example.com")
    from core.config import get_settings

    get_settings.cache_clear()
    try:
        from web.main import create_app

        app = create_app()
        paths = {route.path for route in app.routes}
        assert "/docs" not in paths
        assert "/redoc" not in paths
        assert "/openapi.json" not in paths
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_docs_endpoints_available_in_development():
    from core.config import get_settings

    get_settings.cache_clear()
    from web.main import create_app

    app = create_app()
    paths = {route.path for route in app.routes}
    assert "/docs" in paths
    get_settings.cache_clear()


async def test_security_headers_present_on_every_response(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/health")

    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]
    assert "max-age" in resp.headers["strict-transport-security"]


async def test_untrusted_host_header_is_rejected(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/health", headers={"Host": "evil-attacker.example"})

    assert resp.status_code == 400


def test_www_variant_of_web_base_url_is_trusted(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("WEB_BASE_URL", "https://shivir.online")
    from core.config import get_settings

    get_settings.cache_clear()
    try:
        from web.main import _trusted_hosts

        hosts = _trusted_hosts(get_settings())
        assert "shivir.online" in hosts
        assert "www.shivir.online" in hosts
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
