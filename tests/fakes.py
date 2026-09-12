"""Lightweight aiogram-shaped fakes for testing handlers as plain async
functions, without spinning up a real Bot/Dispatcher/network connection."""


class FakeUser:
    def __init__(self, user_id: int, language_code: str = "en", first_name: str = "Test"):
        self.id = user_id
        self.language_code = language_code
        self.first_name = first_name


class FakeMessage:
    def __init__(self, user_id: int, text: str = "", language_code: str = "en"):
        self.from_user = FakeUser(user_id, language_code)
        self.text = text
        self.sent: list[dict] = []
        self.edited: list[dict] = []
        self.photos: list[dict] = []

    async def answer(self, text, reply_markup=None, parse_mode=None):
        self.sent.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode})
        return self

    async def edit_text(self, text, reply_markup=None, parse_mode=None):
        self.edited.append({"text": text, "reply_markup": reply_markup, "parse_mode": parse_mode})
        return self

    async def answer_photo(self, photo, caption=None):
        self.photos.append({"photo": photo, "caption": caption})
        return self

    @property
    def last_text(self) -> str:
        record = (self.edited or self.sent)[-1]
        return record["text"]


class FakeBot:
    """Duck-typed stand-in for aiogram's Bot — avoids needing a real token or
    network access in tests. `send_message` can be scripted to raise, to
    exercise the notification worker's retry/backoff/blocked-sender paths."""

    def __init__(self, side_effects: list | None = None):
        self.sent: list[dict] = []
        self._side_effects = list(side_effects or [])

    async def send_message(self, chat_id: int, text: str):
        if self._side_effects:
            effect = self._side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
        self.sent.append({"chat_id": chat_id, "text": text})


class FakeCallbackQuery:
    def __init__(self, user_id: int, data: str, message: FakeMessage):
        self.from_user = FakeUser(user_id)
        self.data = data
        self.message = message
        self.answers: list[dict] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append({"text": text, "show_alert": show_alert})
