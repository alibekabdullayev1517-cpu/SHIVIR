"""Personal-link lifecycle: create, look up, regenerate/disable."""

from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.link_prompts import DEFAULT_KEY, is_valid_key
from core.models import PublicLink, User


async def get_or_create_user(session: AsyncSession, tg_user_id: int, lang: str = "uz") -> User:
    """Same check-then-insert race as create_link()/regenerate_link() below —
    concurrent calls for the same tg_user_id (e.g. Telegram redelivering an
    update, or two overlapping handler invocations) can both see no existing
    row and both try to insert one. tg_user_id is the primary key, so the
    loser gets an IntegrityError rather than silently overwriting anything;
    on that, return whichever row actually won instead of raising."""
    user = await session.get(User, tg_user_id)
    if user is not None:
        return user

    user = User(tg_user_id=tg_user_id, lang=lang)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        winner = await session.get(User, tg_user_id)
        if winner is not None:
            return winner
        raise
    return user


async def set_display_name(session: AsyncSession, user: User, display_name: str | None) -> None:
    """Stores the recipient's own Telegram first name, for their own sender
    page's personalization ("Bu odamga anonim xabar yuboring" needs *someone*
    to refer to). This is the account owner's own public first name, supplied
    by them via Telegram — not sender identity, and not stored for anyone else."""
    if not display_name:
        return
    settings = dict(user.settings or {})
    if settings.get("display_name") != display_name:
        settings["display_name"] = display_name
        user.settings = settings
        await session.commit()


def is_paused(user: User | None) -> bool:
    """Owner-controlled pause: the link keeps existing (and stays the same
    link) but accepts no new messages. Deliberately NOT `PublicLink.active`:
    that flag means "replaced or disabled by moderation", and create_link()
    would instantly mint a fresh active link for an owner who has none —
    silently undoing a pause."""
    return bool(user and (user.settings or {}).get("paused") is True)


async def set_paused(session: AsyncSession, user: User, paused: bool) -> bool:
    """Returns True if the state actually changed (so callers only record an
    analytics event on a real transition, not on a double tap)."""
    if is_paused(user) == paused:
        return False
    settings = dict(user.settings or {})
    if paused:
        settings["paused"] = True
    else:
        settings.pop("paused", None)
    user.settings = settings  # reassign: SQLAlchemy doesn't track in-place JSON edits
    await session.commit()
    return True


def get_prompt_key(user: User | None) -> str:
    key = (user.settings or {}).get("prompt") if user else None
    return key if is_valid_key(key) else DEFAULT_KEY


async def set_prompt_key(session: AsyncSession, user: User, key: str) -> bool:
    """Stores a preset key (or clears it for DEFAULT_KEY). Rejects anything that
    isn't an allow-listed preset — the caller passes callback data straight in,
    so this is the validation boundary. Returns True if it changed."""
    if key != DEFAULT_KEY and not is_valid_key(key):
        raise ValueError("unknown prompt preset")
    if get_prompt_key(user) == key:
        return False
    settings = dict(user.settings or {})
    if key == DEFAULT_KEY:
        settings.pop("prompt", None)
    else:
        settings["prompt"] = key
    user.settings = settings
    await session.commit()
    return True


async def has_any_link(session: AsyncSession, owner_user_id: int) -> bool:
    """Whether this owner has ever created a link before (active or not) —
    distinguishes the viral-loop's `new_link_created` signal (a person who
    discovered Shivir via a share and created their first-ever link) from the
    general `link_created` event, which fires on every creation."""
    result = await session.execute(
        select(PublicLink.id).where(PublicLink.owner_user_id == owner_user_id).limit(1)
    )
    return result.scalars().first() is not None


async def get_active_link_for_owner(session: AsyncSession, owner_user_id: int) -> PublicLink | None:
    result = await session.execute(
        select(PublicLink).where(
            PublicLink.owner_user_id == owner_user_id,
            PublicLink.active.is_(True),
        )
    )
    return result.scalars().first()


async def create_link(session: AsyncSession, owner_user_id: int) -> PublicLink:
    """Generate (or return the existing) personal link — zero form-filling, per spec.

    The check-then-insert below is a TOCTOU race under concurrent requests
    (e.g. a double-tapped button hitting two DB connections at once); the
    partial unique index on (owner_user_id) WHERE active is the actual
    guard — on a lost race we catch the IntegrityError and return whichever
    row won, rather than erroring out or leaving two active links.
    """
    existing = await get_active_link_for_owner(session, owner_user_id)
    if existing is not None:
        return existing

    link = PublicLink(owner_user_id=owner_user_id)
    session.add(link)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        winner = await get_active_link_for_owner(session, owner_user_id)
        if winner is not None:
            return winner
        raise  # genuinely unexpected — not the race we know about
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
    try:
        await session.commit()
    except IntegrityError:
        # Lost a concurrent regenerate/create race — the partial unique index
        # is the real guard here (see create_link()). Whichever row is now
        # active for this owner is the correct one to hand back.
        await session.rollback()
        winner = await get_active_link_for_owner(session, owner_user_id)
        if winner is not None:
            return winner
        raise
    await session.refresh(new_link)
    return new_link


async def auto_disable_link(session: AsyncSession, link: PublicLink) -> None:
    link.active = False
    await session.commit()


def build_sender_url(web_base_url: str, token: str) -> str:
    return f"{web_base_url.rstrip('/')}/s/{token}"


def build_telegram_share_url(sender_url: str, share_text: str) -> str:
    """Telegram's own share deep link — tapping it opens the client's native
    forward/share picker with `share_text` + `sender_url` pre-filled; the
    user still explicitly chooses who to send it to and taps send
    themselves. `sender_url` must already be a real, generated sender URL
    (see build_sender_url) — never a placeholder or altered value."""
    return f"https://t.me/share/url?url={quote(sender_url, safe='')}&text={quote(share_text, safe='')}"
