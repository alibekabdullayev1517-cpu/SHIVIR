"""Bot entrypoint — long polling (no public HTTPS endpoint required for dev;
switch to webhook mode at deploy time per infra/ docs)."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis

from cards.render import warm_up as warm_up_cards
from core.config import get_settings

from bot.error_handler import on_error
from bot.handlers import inbox, moderation, settings as settings_handlers, start
from bot.middlewares import DbSessionMiddleware


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set — supply it via the environment (.env), never hardcode it.")

    logging.basicConfig(level=settings.log_level)

    # Build the share card's cached static layer + fonts now, so the first
    # "Karta sifatida" tap isn't slower than the rest. Best-effort only.
    try:
        await asyncio.to_thread(warm_up_cards)
    except Exception:
        logging.getLogger("shivir.bot").warning("Share-card warm-up failed; first card will build lazily", exc_info=True)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    dp.include_router(inbox.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(moderation.router)

    # Without this, an unhandled exception (e.g. Telegram's own
    # "message is not modified" on a double-tapped button) leaves the tap
    # looking dead to the user — see bot/error_handler.py.
    dp.errors.register(on_error)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    await bot.delete_webhook(drop_pending_updates=False)
    try:
        # close_bot_session=True (the default) already closes `bot`'s session
        # on shutdown; `redis` is ours to close.
        await dp.start_polling(bot, settings=settings, redis=redis)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
