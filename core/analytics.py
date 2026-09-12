"""Single entry point for writing analytics events (the master plan's event
taxonomy). Every call site goes through this instead of writing to the events
table directly, so the shape stays consistent and future dashboarding has one
place to reason about.

Sender-side events (link_clicked, sender_page_viewed, message_started,
abuse_warning_shown, send_rate_limited, message_sent) must never carry anything
that could deanonymize the sender — no fingerprint hash, no IP, no user agent.
"""

from core.db import session_scope
from core.models import Event


async def track(name: str, *, user_id: int | None = None, **props) -> None:
    async with session_scope() as session:
        session.add(Event(name=name, user_id=user_id, props=props))
        await session.commit()
