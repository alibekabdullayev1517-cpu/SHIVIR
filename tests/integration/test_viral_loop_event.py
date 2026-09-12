"""new_link_created must fire exactly once — on a user's first-ever link —
distinguishing the viral-loop signal from the general link_created event that
fires on every creation (including regeneration)."""

from sqlalchemy import select

from core.config import get_settings
from core.models import Event

from bot.handlers import start
from tests.fakes import FakeCallbackQuery, FakeMessage

settings = get_settings()


async def test_new_link_created_fires_once_on_first_link(db_session, clean_tables):
    fake_msg = FakeMessage(user_id=6001)
    cb = FakeCallbackQuery(user_id=6001, data="link:create", message=fake_msg)

    await start.on_create_link(cb, db_session, settings)

    result = await db_session.execute(select(Event).where(Event.name == "new_link_created"))
    assert len(result.scalars().all()) == 1

    result2 = await db_session.execute(select(Event).where(Event.name == "link_created"))
    assert len(result2.scalars().all()) == 1


async def test_new_link_created_does_not_fire_again_on_idempotent_recreate(db_session, clean_tables):
    fake_msg = FakeMessage(user_id=6002)
    cb1 = FakeCallbackQuery(user_id=6002, data="link:create", message=fake_msg)
    await start.on_create_link(cb1, db_session, settings)

    cb2 = FakeCallbackQuery(user_id=6002, data="link:create", message=fake_msg)
    await start.on_create_link(cb2, db_session, settings)

    result = await db_session.execute(select(Event).where(Event.name == "new_link_created"))
    assert len(result.scalars().all()) == 1  # not fired twice

    result2 = await db_session.execute(select(Event).where(Event.name == "link_created"))
    assert len(result2.scalars().all()) == 2  # general event still fires each time
