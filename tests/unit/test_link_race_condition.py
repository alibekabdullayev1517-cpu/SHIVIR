"""Regression test for a real TOCTOU race in create_link()/regenerate_link():
concurrent requests from the same user (e.g. a double-tapped button) used to
be able to create two simultaneously-active links, since the check
("does an active link exist?") and the insert weren't atomic. Fixed with a
partial unique index (core/models.py) plus IntegrityError handling.
"""

import asyncio

from sqlalchemy import func, select

from core.db import SessionLocal
from core.models import PublicLink, User
from core.services.links import create_link, get_or_create_user, regenerate_link


async def test_concurrent_create_link_never_produces_two_active_links(db_session, clean_tables):
    await get_or_create_user(db_session, 20001)

    # Each concurrent call gets its OWN session/connection — a single shared
    # AsyncSession isn't safe for concurrent use and wouldn't exercise the
    # real race (which only shows up across separate DB connections).
    async def _create():
        async with SessionLocal() as session:
            return await create_link(session, owner_user_id=20001)

    results = await asyncio.gather(*(_create() for _ in range(8)))

    assert len({r.token for r in results}) == 1  # everyone got the same link

    async with SessionLocal() as session:
        count = await session.execute(
            select(func.count(PublicLink.id)).where(
                PublicLink.owner_user_id == 20001, PublicLink.active.is_(True)
            )
        )
        assert count.scalar_one() == 1


async def test_concurrent_regenerate_link_never_produces_two_active_links(db_session, clean_tables):
    await get_or_create_user(db_session, 20002)
    await create_link(db_session, owner_user_id=20002)

    async def _regenerate():
        async with SessionLocal() as session:
            return await regenerate_link(session, owner_user_id=20002)

    results = await asyncio.gather(*(_regenerate() for _ in range(6)))

    assert all(r is not None for r in results)

    async with SessionLocal() as session:
        count = await session.execute(
            select(func.count(PublicLink.id)).where(
                PublicLink.owner_user_id == 20002, PublicLink.active.is_(True)
            )
        )
        assert count.scalar_one() == 1
