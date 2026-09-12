from core.models import User
from core.services.links import (
    create_link,
    get_active_link_for_owner,
    get_link_by_token,
    regenerate_link,
)


async def test_create_link_generates_unique_token(db_session, clean_tables):
    db_session.add(User(tg_user_id=1))
    await db_session.commit()

    link = await create_link(db_session, owner_user_id=1)

    assert link.token
    assert len(link.token) >= 16
    assert link.active is True


async def test_create_link_is_idempotent_for_same_owner(db_session, clean_tables):
    db_session.add(User(tg_user_id=2))
    await db_session.commit()

    first = await create_link(db_session, owner_user_id=2)
    second = await create_link(db_session, owner_user_id=2)

    assert first.id == second.id
    assert first.token == second.token


async def test_get_link_by_token_roundtrip(db_session, clean_tables):
    db_session.add(User(tg_user_id=3))
    await db_session.commit()
    created = await create_link(db_session, owner_user_id=3)

    found = await get_link_by_token(db_session, created.token)

    assert found is not None
    assert found.id == created.id


async def test_regenerate_link_invalidates_old_and_issues_new(db_session, clean_tables):
    db_session.add(User(tg_user_id=4))
    await db_session.commit()
    old = await create_link(db_session, owner_user_id=4)

    new = await regenerate_link(db_session, owner_user_id=4)

    await db_session.refresh(old)
    assert old.active is False
    assert new.token != old.token
    assert new.active is True

    active = await get_active_link_for_owner(db_session, owner_user_id=4)
    assert active.id == new.id
