# tests/helpers/fake_aiogram_module.py
from types import SimpleNamespace

class _FakeAttr:
    """Имитация aiogram.F — поддерживает цепочки .data.startswith(...) и т.п."""
    def __init__(self, name=""):
        self._name = name

    def __getattr__(self, item):
        return _FakeAttr(f"{self._name}.{item}" if self._name else item)

    def __call__(self, *a, **kw):
        return self

    def startswith(self, *a, **kw):
        return self

    def __repr__(self):
        return f"<FakeF {self._name}>"

# --- Message / CallbackQuery / FSMContext ---
class FakeMessage:
    def __init__(self, text="/start", chat_id: int = 1, username: str = "test_user", **extra):
        self.text = text
        self.chat = SimpleNamespace(id=chat_id)
        self.from_user = SimpleNamespace(id=chat_id, username=username)
        self.extra = extra
        # storage for assertions
        self._last_answer = None
        self._last_reply = None
        self._last_edit = None

    async def answer(self, text, **kwargs):
        self._last_answer = (text, kwargs)
        return SimpleNamespace(text=text)

    async def reply(self, text, **kwargs):
        self._last_reply = (text, kwargs)
        return SimpleNamespace(text=text)

    async def edit_text(self, text, **kwargs):
        self._last_edit = (text, kwargs)
        return SimpleNamespace(text=text)

    def set(self, **kwargs):
        """Удобно менять поля на лету: text, chat_id, username и т.д."""
        for k, v in kwargs.items():
            if k == "text":
                self.text = v
            elif k == "chat_id":
                self.chat.id = v
                self.from_user.id = v
            elif k == "username":
                self.from_user.username = v
            else:
                setattr(self, k, v)
        return self

class FakeCallbackQuery:
    def __init__(self, data="callback_data", chat_id: int = 1, username: str = "test_user"):
        self.data = data
        self.from_user = SimpleNamespace(id=chat_id, username=username)
        self.message = None

    async def answer(self, *a, **kw):
        return None

class FakeFSMContext:
    async def clear(self): ...
    async def set_state(self, *a, **kw): ...
    async def update_data(self, **kw): ...
    async def get_data(self): return {}

# --- Router (реализует декораторы) ---
class FakeRouter:
    def __init__(self):
        self._registered_messages = []
        self._registered_callbacks = []

    def message(self, *filters, **kwargs):
        def decorator(handler):
            self._registered_messages.append((filters, handler))
            return handler
        return decorator

    def callback_query(self, *filters, **kwargs):
        def decorator(handler):
            self._registered_callbacks.append((filters, handler))
            return handler
        return decorator

    def include_router(self, *a, **kw):
        pass

# --- Bot / Dispatcher / keyboard classes ---
class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=text)

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.sent.append((chat_id, caption if caption is not None else "", kwargs))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=caption)

    def clear(self):
        self.sent.clear()

    def get_message(self, chat_id: int, text: str) -> bool:
        return any(c == chat_id and t == text for c, t, _ in self.sent)

    def check_str_in_messages(self, text: str):
        return any(text in t for _, t, _ in self.sent)

class FakeDispatcher:
    pass

class InlineKeyboardButton:
    def __init__(self, text=None, callback_data=None, url=None, **kw):
        self.text = text
        self.callback_data = callback_data
        self.url = url

class InlineKeyboardMarkup:
    def __init__(self, inline_keyboard=None, **kw):
        self.inline_keyboard = inline_keyboard or []

class KeyboardButton:
    def __init__(self, text=None, **kw):
        self.text = text

class ReplyKeyboardMarkup:
    def __init__(self, keyboard=None, resize_keyboard=None, input_field_placeholder=None, **kw):
        self.keyboard = keyboard or []
        self.resize_keyboard = resize_keyboard
        self.input_field_placeholder = input_field_placeholder

class ReplyKeyboardRemove:
    def __init__(self, remove_keyboard: bool = True, selective: bool = False):
        self.remove_keyboard = remove_keyboard
        self.selective = selective

class ForceReply:
    def __init__(self, force: bool = True, selective: bool = False):
        self.force = force
        self.selective = selective

class InlineKeyboardBuilder:
    def __init__(self):
        self._buttons = []

    def add(self, *buttons):
        self._buttons.extend(buttons)

    def adjust(self, *a, **kw):
        pass

    def as_markup(self):
        return self._buttons
