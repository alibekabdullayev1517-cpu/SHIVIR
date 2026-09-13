"""Global error handler for the dispatcher.

Without this, aiogram's default behavior for ANY unhandled exception in a
handler is to log it and silently drop the update — the bot process itself
never crashes (verified by reading aiogram's dispatcher internals), but the
user who tapped a button sees nothing happen at all, which reads as broken.

The single most common real-world case is Telegram's own
"message is not modified" error: a user double-taps a button (e.g. "Inbox")
while the screen already shows that exact content. That's not a bug, so it
shouldn't be logged as one or leave the tap looking dead.
"""

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

logger = logging.getLogger("shivir.bot")

_NOT_MODIFIED = "message is not modified"


async def on_error(event: ErrorEvent) -> bool:
    exc = event.exception
    callback = event.update.callback_query

    if isinstance(exc, TelegramBadRequest) and _NOT_MODIFIED in str(exc):
        logger.debug("Ignored idempotent edit (message is not modified).")
    else:
        logger.error(
            "Unhandled error processing update %s: %s: %s",
            event.update.update_id,
            exc.__class__.__name__,
            exc,
            exc_info=exc,
        )

    if callback is not None:
        try:
            await callback.answer()
        except Exception:
            pass  # best-effort only — never let error recovery itself raise

    return True  # handled: stop aiogram's own default fallback logging
