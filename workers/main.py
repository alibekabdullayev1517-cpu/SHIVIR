"""Notification worker entrypoint — run as its own process in deployment
(see infra/systemd/shivir-worker.service.example)."""

import asyncio
import logging

from aiogram import Bot
from redis.asyncio import Redis

from core.config import get_settings
from core.db import SessionLocal

from workers.notifier import run_forever


async def main() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not set — supply it via the environment (.env), never hardcode it.")

    logging.basicConfig(level=settings.log_level)

    bot = Bot(token=settings.bot_token)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    try:
        await run_forever(bot, SessionLocal, redis)
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
