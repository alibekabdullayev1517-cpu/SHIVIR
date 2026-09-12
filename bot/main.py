"""Bot entrypoint — long polling (no public HTTPS endpoint required for dev;
switch to webhook mode at deploy time per infra/ docs)."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from redis.asyncio import Redis

from core.config import get_settings

from bot.handlers import inbox, moderation, settings as settings_handlers, start
from bot.middlewares import DbSessionMiddleware


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set — supply it via the environment (.env), never hardcode it.")

    logging.basicConfig(level=settings.log_level)

    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    dp.include_router(inbox.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(moderation.router)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, settings=settings, redis=redis)


if __name__ == "__main__":
    asyncio.run(main())
