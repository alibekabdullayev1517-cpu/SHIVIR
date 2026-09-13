"""Regression tests for bot/error_handler.py.

Without it, an unhandled exception (most commonly Telegram's
"message is not modified" on a double-tapped button) leaves the tap looking
dead with no user feedback. And until the P2 fix below, a *message*-type
update (e.g. /start, /modqueue) that raised got no response at all —
callback.answer() only ever covered button taps.
"""

from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest

from bot.error_handler import on_error
from tests.fakes import FakeBot


class _FakeMethod:
    """Minimal stand-in for the aiogram TelegramMethod a real
    TelegramBadRequest wraps — only str() rendering is exercised."""

    def __repr__(self):
        return "editMessageText(...)"


def _make_event(exception: Exception, with_callback: bool = True, with_message: bool = False):
    callback = SimpleNamespace(answered=False)

    async def _answer():
        callback.answered = True

    cb = None
    if with_callback:
        callback.answer = _answer
        cb = callback

    message = None
    if with_message:
        message = SimpleNamespace(chat=SimpleNamespace(id=42))

    update = SimpleNamespace(update_id=12345, callback_query=cb, message=message)
    return SimpleNamespace(exception=exception, update=update), callback, message


async def test_not_modified_error_is_suppressed_and_callback_answered():
    exc = TelegramBadRequest(method=_FakeMethod(), message="Bad Request: message is not modified")
    event, callback, _ = _make_event(exc)
    bot = FakeBot()

    handled = await on_error(event, bot)

    assert handled is True
    assert callback.answered is True
    assert bot.sent == []  # callback flow never also sends a message


async def test_generic_exception_is_logged_and_suppressed_not_reraised():
    event, callback, _ = _make_event(RuntimeError("something unexpected"))
    bot = FakeBot()

    handled = await on_error(event, bot)

    assert handled is True  # never re-raises — a bug elsewhere can't take the bot down
    assert callback.answered is True


async def test_missing_callback_query_does_not_crash_the_handler():
    event, _, _ = _make_event(RuntimeError("boom"), with_callback=False)
    bot = FakeBot()

    handled = await on_error(event, bot)

    assert handled is True
    assert bot.sent == []  # no message on the update either — nothing to reply to


async def test_callback_answer_failure_is_swallowed():
    """If even the best-effort callback.answer() fails (e.g. the callback is
    too old), the error handler itself must not raise."""
    exc = TelegramBadRequest(method=_FakeMethod(), message="message is not modified")
    event, callback, _ = _make_event(exc)
    bot = FakeBot()

    async def _raise():
        raise RuntimeError("callback expired")

    callback.answer = _raise

    handled = await on_error(event, bot)
    assert handled is True


# --- P2: message-type updates used to get no response at all ---


async def test_message_type_update_error_gets_generic_fallback_reply():
    event, _, message = _make_event(RuntimeError("boom"), with_callback=False, with_message=True)
    bot = FakeBot()

    handled = await on_error(event, bot)

    assert handled is True
    assert len(bot.sent) == 1
    assert bot.sent[0]["chat_id"] == message.chat.id
    assert bot.sent[0]["text"]  # non-empty, plain-language generic copy


async def test_message_type_update_fallback_never_raises_on_send_failure():
    """The fallback send is itself best-effort — a failure there (e.g. the
    user blocked the bot) must not propagate out of the error handler."""
    event, _, _ = _make_event(RuntimeError("boom"), with_callback=False, with_message=True)
    bot = FakeBot(side_effects=[RuntimeError("network blip")])

    handled = await on_error(event, bot)
    assert handled is True


async def test_message_type_update_fallback_reply_has_no_parse_mode():
    """Defense in depth: even though this text is our own copy (not
    user-controlled), never give a future edit an accidental markup vector."""
    event, _, _ = _make_event(RuntimeError("boom"), with_callback=False, with_message=True)
    bot = FakeBot()

    await on_error(event, bot)

    assert bot.sent[0]["parse_mode"] is None


async def test_neither_callback_nor_message_present_sends_nothing():
    """Some update types (e.g. a channel post) carry neither — must not
    crash and must not attempt to reply anywhere."""
    event, _, _ = _make_event(RuntimeError("boom"), with_callback=False, with_message=False)
    bot = FakeBot()

    handled = await on_error(event, bot)

    assert handled is True
    assert bot.sent == []
