"""Regression tests for bot/error_handler.py — without it, an unhandled
exception (most commonly Telegram's "message is not modified" on a
double-tapped button) leaves the tap looking dead with no user feedback."""

from types import SimpleNamespace

from aiogram.exceptions import TelegramBadRequest

from bot.error_handler import on_error


class _FakeMethod:
    """Minimal stand-in for the aiogram TelegramMethod a real
    TelegramBadRequest wraps — only str() rendering is exercised."""

    def __repr__(self):
        return "editMessageText(...)"


def _make_event(exception: Exception, with_callback: bool = True):
    callback = SimpleNamespace(answered=False)

    async def _answer():
        callback.answered = True

    if with_callback:
        callback.answer = _answer
        cb = callback
    else:
        cb = None

    update = SimpleNamespace(update_id=12345, callback_query=cb)
    return SimpleNamespace(exception=exception, update=update), callback


async def test_not_modified_error_is_suppressed_and_callback_answered():
    exc = TelegramBadRequest(method=_FakeMethod(), message="Bad Request: message is not modified")
    event, callback = _make_event(exc)

    handled = await on_error(event)

    assert handled is True
    assert callback.answered is True


async def test_generic_exception_is_logged_and_suppressed_not_reraised():
    event, callback = _make_event(RuntimeError("something unexpected"))

    handled = await on_error(event)

    assert handled is True  # never re-raises — a bug elsewhere can't take the bot down
    assert callback.answered is True


async def test_missing_callback_query_does_not_crash_the_handler():
    event, _ = _make_event(RuntimeError("boom"), with_callback=False)

    handled = await on_error(event)

    assert handled is True


async def test_callback_answer_failure_is_swallowed():
    """If even the best-effort callback.answer() fails (e.g. the callback is
    too old), the error handler itself must not raise."""
    exc = TelegramBadRequest(method=_FakeMethod(), message="message is not modified")
    event, callback = _make_event(exc)

    async def _raise():
        raise RuntimeError("callback expired")

    callback.answer = _raise

    handled = await on_error(event)
    assert handled is True
