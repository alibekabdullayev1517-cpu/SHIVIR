"""/s/<token>/track — the anonymous analytics beacon — must not be a way to flood
the events table, and must not interfere with real sending."""

import re

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import func, select

from core.config import get_settings
from core.models import Event, Message, User
from core.services.links import create_link

settings = get_settings()


@pytest_asyncio.fixture
async def client(fake_redis):
    from web.main import app

    app.state.redis = fake_redis
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def limits(monkeypatch):
    """Tighten the beacon limits for a test; restored automatically."""
    def apply(per_fp: int = 3, global_: int = 1000):
        monkeypatch.setattr(settings, "rate_limit_track_per_fingerprint", per_fp)
        monkeypatch.setattr(settings, "rate_limit_track_global", global_)
    return apply


async def _link(db_session, tg_id: int):
    db_session.add(User(tg_user_id=tg_id, lang="uz"))
    await db_session.commit()
    return await create_link(db_session, owner_user_id=tg_id)


async def _count(db_session, name: str | None = None) -> int:
    stmt = select(func.count(Event.id))
    if name:
        stmt = stmt.where(Event.name == name)
    return (await db_session.execute(stmt)).scalar_one()


def _from(ip: str) -> dict:
    return {"x-forwarded-for": ip, "user-agent": "TestBrowser/1.0"}


def _csrf(html: str) -> str:
    return re.search(r'const csrfToken = "([^"]+)"', html).group(1)


async def test_valid_events_are_accepted_and_stored(client, db_session, clean_tables):
    link = await _link(db_session, 9701)
    a = await client.post(f"/s/{link.token}/track", json={"name": "message_started"})
    b = await client.post(f"/s/{link.token}/track", json={"name": "sender_cta_clicked"})
    assert a.status_code == b.status_code == 200 and a.json() == b.json() == {"status": "ok"}
    assert await _count(db_session, "message_started") == 1 and await _count(db_session, "sender_cta_clicked") == 1


async def test_invalid_events_are_rejected_and_never_use_up_the_budget(client, db_session, limits, clean_tables):
    limits(per_fp=2)
    link = await _link(db_session, 9702)
    for junk in ({"name": "drop_table"}, {"name": None}, {"name": ["message_started"]}, {}, [], "x", 5):
        r = await client.post(f"/s/{link.token}/track", json=junk)
        assert r.status_code == 200 and r.json() == {"status": "ignored"}
    assert (await client.post(f"/s/{link.token}/track", content=b"not json")).json() == {"status": "ignored"}
    assert await _count(db_session) == 0
    # 9 junk requests later, the visitor's real budget of 2 is untouched
    for _ in range(2):
        assert (await client.post(f"/s/{link.token}/track", json={"name": "message_started"})).status_code == 200
    assert await _count(db_session, "message_started") == 2


async def test_repeated_abuse_is_throttled_and_the_event_count_stays_bounded(client, db_session, limits, clean_tables):
    limits(per_fp=3)
    link = await _link(db_session, 9703)
    statuses = [
        (await client.post(f"/s/{link.token}/track", json={"name": "message_started"}, headers=_from("192.0.2.1"))).status_code
        for _ in range(50)
    ]
    assert statuses[:3] == [200, 200, 200] and set(statuses[3:]) == {429}
    assert await _count(db_session) == 3  # 50 requests, 3 rows: the table cannot be flooded
    body = (await client.post(f"/s/{link.token}/track", json={"name": "message_started"}, headers=_from("192.0.2.1"))).json()
    assert body == {"status": "rate_limited"}


async def test_other_visitors_are_not_affected_by_one_abuser(client, db_session, limits, clean_tables):
    limits(per_fp=2)
    link = await _link(db_session, 9704)
    for _ in range(10):
        await client.post(f"/s/{link.token}/track", json={"name": "message_started"}, headers=_from("192.0.2.10"))
    ok = await client.post(f"/s/{link.token}/track", json={"name": "message_started"}, headers=_from("192.0.2.11"))
    assert ok.status_code == 200  # a different fingerprint has its own budget


async def test_global_cap_bounds_a_distributed_flood(client, db_session, limits, clean_tables):
    limits(per_fp=100, global_=5)
    link = await _link(db_session, 9705)
    codes = [
        (await client.post(f"/s/{link.token}/track", json={"name": "message_started"}, headers=_from(f"198.51.100.{i}"))).status_code
        for i in range(12)  # 12 different sources
    ]
    assert codes.count(200) == 5 and codes.count(429) == 7
    assert await _count(db_session) == 5


async def test_unknown_tokens_are_throttled_too_and_store_nothing(client, db_session, limits, clean_tables):
    limits(per_fp=2)
    codes = [(await client.post(f"/s/guess-{i}/track", json={"name": "message_started"})).status_code for i in range(6)]
    assert codes == [200, 200, 429, 429, 429, 429]
    assert await _count(db_session) == 0


async def test_beacon_and_sending_have_separate_budgets(client, db_session, fake_redis, limits, monkeypatch, clean_tables):
    """Exhausting the beacon must not stop a real message, and sending must not use up the beacon."""
    limits(per_fp=2)
    monkeypatch.setattr(settings, "rate_limit_send_per_fingerprint", 1)
    link = await _link(db_session, 9706)
    token = link.token
    page = await client.get(f"/s/{token}")
    for _ in range(5):
        await client.post(f"/s/{token}/track", json={"name": "message_started"})
    assert (await client.post(f"/s/{token}/track", json={"name": "message_started"})).status_code == 429

    sent = await client.post(f"/s/{token}/send", json={"message": "salom", "csrf_token": _csrf(page.text)})
    assert sent.status_code == 200 and sent.json()["status"] == "success"      # sending unaffected
    assert (await db_session.execute(select(func.count(Message.id)))).scalar_one() == 1

    other = "203.0.113.9"  # fresh visitor: sending does not consume the beacon budget
    p2 = await client.get(f"/s/{token}", headers=_from(other))
    await client.post(f"/s/{token}/send", json={"message": "yana salom", "csrf_token": _csrf(p2.text)}, headers=_from(other))
    assert (await client.post(f"/s/{token}/track", json={"name": "sender_cta_clicked"}, headers=_from(other))).status_code == 200


async def test_normal_page_visit_is_far_below_the_default_limits(client, db_session, clean_tables):
    assert settings.rate_limit_track_per_fingerprint >= 30 and settings.rate_limit_track_global >= 1000
    link = await _link(db_session, 9707)
    for name in ("message_started", "sender_cta_clicked", "message_started", "sender_cta_clicked"):
        assert (await client.post(f"/s/{link.token}/track", json={"name": name})).status_code == 200


async def test_limiter_state_is_anonymous_and_expires(client, db_session, fake_redis, clean_tables):
    ip = "203.0.113.200"
    link = await _link(db_session, 9708)
    await client.post(f"/s/{link.token}/track", json={"name": "sender_cta_clicked"}, headers=_from(ip))

    keys = sorted([k async for k in fake_redis.scan_iter("rl:track:*")])
    assert len(keys) == 2 and keys[1] == "rl:track:global"
    assert re.fullmatch(r"rl:track:fp:[0-9a-f]{32}", keys[0])                       # only the anonymous hash
    assert all(ip not in k and "TestBrowser" not in k for k in keys)                # never the raw IP / UA
    for key in keys:
        assert await fake_redis.ttl(key) > 0                                        # counters expire on their own
    (event,) = (await db_session.execute(select(Event).where(Event.name == "sender_cta_clicked"))).scalars().all()
    assert event.user_id is None and event.props == {}                             # nothing new is recorded about the visitor


async def test_limiter_failure_drops_the_event_instead_of_erroring_or_writing(client, db_session, monkeypatch, clean_tables):
    import web.routes.sender as sender_module

    async def broken(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr(sender_module, "check_track_rate_limit", broken)
    link = await _link(db_session, 9709)
    resp = await client.post(f"/s/{link.token}/track", json={"name": "message_started"})
    assert resp.status_code == 200 and resp.json() == {"status": "ignored"}       # never a 500 for a beacon
    assert await _count(db_session) == 0                                            # and no unbounded writes
    # sending is unaffected by the beacon's limiter being down
    page = await client.get(f"/s/{link.token}")
    sent = await client.post(f"/s/{link.token}/send", json={"message": "salom", "csrf_token": _csrf(page.text)})
    assert sent.json()["status"] == "success"
