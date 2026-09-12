from sqlalchemy import select

from core.analytics import track
from core.models import Event, User


async def test_track_writes_event_with_props(db_session, clean_tables):
    await track("link_created", user_id=None, link_id=99)

    result = await db_session.execute(select(Event).where(Event.name == "link_created"))
    event = result.scalars().first()
    assert event is not None
    assert event.props == {"link_id": 99}


async def test_track_associates_user_id(db_session, clean_tables):
    db_session.add(User(tg_user_id=55))
    await db_session.commit()

    await track("bot_started", user_id=55, source="deep_link", is_returning=False)

    result = await db_session.execute(select(Event).where(Event.name == "bot_started"))
    event = result.scalars().first()
    assert event.user_id == 55
    assert event.props["source"] == "deep_link"
