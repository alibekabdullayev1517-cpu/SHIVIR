"""Personal-link lifecycle: create, look up, regenerate/disable."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import PublicLink, User


async def get_or_create_user(session: AsyncSession, tg_user_id: int, lang: str = "uz") -> User:
    user = await session.get(User, tg_user_id)
    if user is None:
        user = User(tg_user_id=tg_user_id, lang=lang)
        session.add(user)
        await session.commit()
    return user


async def get_active_link_for_owner(session: AsyncSession, owner_user_id: int) -> PublicLink | None:
    result = await session.execute(
        select(PublicLink).where(
            PublicLink.owner_user_id == owner_user_id,
            PublicLink.active.is_(True),
        )
    )
    return result.scalars().first()


async def create_link(session: AsyncSession, owner_user_id: int) -> PublicLink:
    """Generate (or return the existing) personal link — zero form-filling, per spec."""
    existing = await get_active_link_for_owner(session, owner_user_id)
    if existing is not None:
        return existing

    link = PublicLink(owner_user_id=owner_user_id)
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


async def get_link_by_token(session: AsyncSession, token: str) -> PublicLink | None:
    result = await session.execute(select(PublicLink).where(PublicLink.token == token))
    return result.scalars().first()


async def regenerate_link(
    session: AsyncSession, owner_user_id: int, reason: str = "user_initiated"
) -> PublicLink:
    """Invalidate the old link and issue a new one. Old link's messages stay in the
    recipient's inbox — only `public_links.active` changes, `messages.link_id`
    references are untouched."""
    old = await get_active_link_for_owner(session, owner_user_id)
    if old is not None:
        old.active = False

    new_link = PublicLink(owner_user_id=owner_user_id)
    session.add(new_link)
    await session.commit()
    await session.refresh(new_link)
    return new_link


async def auto_disable_link(session: AsyncSession, link: PublicLink) -> None:
    link.active = False
    await session.commit()


def build_sender_url(web_base_url: str, token: str) -> str:
    return f"{web_base_url.rstrip('/')}/s/{token}"
