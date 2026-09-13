"""Global error handler for the dispatcher.

Without this, aiogram's default behavior for ANY unhandled exception in a
handler is to log it and silently drop the update — the bot process itself
never crashes (verified by reading aiogram's dispatcher internals), but the
user who triggered it sees nothing happen at all, which reads as broken.

The single most common real-world case is Telegram's own
"message is not modified" error: a user double-taps a button (e.g. "Inbox")
while the screen already shows that exact content. That's not a bug, so it
shouldn't be logged as one or leave the tap looking dead.
"""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

from core.copy import t

logger = logging.getLogger("shivir.bot")

_NOT_MODIFIED = "message is not modified"


async def on_error(event: ErrorEvent, bot: Bot) -> bool:
    exc = event.exception
    callback = event.update.callback_query
    message = event.update.message
    is_not_modified = isinstance(exc, TelegramBadRequest) and _NOT_MODIFIED in str(exc)

    if is_not_modified:
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
    elif message is not None and not is_not_modified:
        # A message-type update (e.g. /start, /modqueue) that raised
        # previously left the sender with no response at all —
        # callback.answer() only covers button taps. One best-effort,
        # generic reply, never a retry. "message is not modified" can only
        # ever come from editing an existing message (a callback flow), so
        # excluding it here is just for clarity, not reachable in practice.
        # parse_mode=None: never risk interpreting anything as markup here.
        try:
            await bot.send_message(chat_id=message.chat.id, text=t("generic_error", "uz"), parse_mode=None)
        except Exception:
            pass  # best-effort only — never let error recovery itself raise

    return True  # handled: stop aiogram's own default fallback logging
