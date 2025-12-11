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


class FakeBaseFilter:
    """Простейшая заглушка BaseFilter для тестов."""
    def __init__(self, *args, **kwargs):
        pass

    async def __call__(self, event, *args, **kwargs):
        """Возвращает True для любых событий."""
        return True


class FakeStatesGroup:
    """Простейшая заглушка StatesGroup для тестов."""
    def __init_subclass__(cls, **kwargs):
        # Позволяет объявлять состояния как в aiogram:
        # class MyState(StatesGroup):
        #     waiting_name = State()
        pass


class FakeState:
    """Простейшая заглушка State для тестов."""
    def __init__(self):
        self.name = None
        self.state = None

    def __set_name__(self, owner, name):
        self.name = name
        self.state = str(name)

    def __repr__(self):
        return f"<State {self.name}>"


class FakeCommandObject:
    """
    Фейковый аналог aiogram.filters.CommandObject.

    Позволяет удобно тестировать команды с аргументами:
        /start ref=ABC123
        /transfer 100 200
    """

    def __init__(self, command: str = "start", args: str | None = None):
        self.command = command
        self.args = args or ""
        self.mention = None  # в реальном CommandObject может быть @username
        self.offset = 0      # смещение в тексте сообщения (не используется в тестах)

    def __repr__(self):
        return f"<FakeCommandObject command={self.command!r} args={self.args!r}>"

    @classmethod
    def from_message(cls, text: str):
        """
        Быстрое создание из строки:
        >>> FakeCommandObject.from_message('/start ref=123')
        """
        if not text.startswith('/'):
            return cls(command=text)
        parts = text[1:].split(maxsplit=1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return cls(command, args)

class FakeTelegramObject:
    """
    Упрощённая версия aiogram.types.TelegramObject.
    Используется как базовый класс для фейковых aiogram-типов.
    """

    def __init__(self, **data):
        # просто сохраняем все переданные поля как атрибуты
        for key, value in data.items():
            setattr(self, key, value)

    def __repr__(self):
        cls = self.__class__.__name__
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"<{cls} {attrs}>"

    def model_dump(self):
        """Имитация pydantic BaseModel.model_dump()"""
        return self.__dict__.copy()

    def copy(self):
        """Возвращает копию объекта"""
        return self.__class__(**self.__dict__)


class FakeDocument:
    def __init__(self):
        pass


class FakeBufferedInputFile:
    def __init__(
        self,
        file: bytes,
        filename: str,
        chunk_size: int = 0
    ):
        pass



class FakeMessage:
    def __init__(self, text="/start", chat_id: int = 1, username: str = "test_user", **extra):
        self.text = text
        self.chat = SimpleNamespace(id=chat_id)
        self.from_user = SimpleNamespace(id=chat_id, username=username)
        self.extra = extra
        self.message_id = 0
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
        self.deleted = False
        self.answer = self.fun_answer

    async def fun_answer(self, *a, **kw):
        return None

    async def fake_delete(self, *a, **kw):
        self.deleted = True

    async def fake_answer(self, text, **kwargs):
        self.answer = text

class FakeFSMContext:
    def __init__(self):
        self.state = None
        self.data = {}

    async def clear(self):
        self.state = None
        self.data = {}

    async def set_state(self, st):
        self.state = st.state

    async def update_data(self, **kw):
        self.data.update(kw)

    async def get_data(self):
        return dict(self.data)

    async def get_state(self):
        return self.state


# --- Router (реализует декораторы) ---
class FakeRouter:
    def __init__(self):
        self._registered_messages = []
        self._registered_callbacks = []
        self._middlewares = {"message": [], "callback_query": []}

        # создаём объекты-подобные aiogram’у
        self.message = _FakeHandlerRegistry(
            self._registered_messages,
            self._middlewares["message"]
        )
        self.callback_query = _FakeHandlerRegistry(
            self._registered_callbacks,
            self._middlewares["callback_query"]
        )

    # --- регистрация хэндлеров ---
    def _register_message(self, *filters, **kwargs):
        def decorator(handler):
            self._registered_messages.append((filters, handler))
            return handler

        return decorator

    def _register_callback(self, *filters, **kwargs):
        def decorator(handler):
            self._registered_callbacks.append((filters, handler))
            return handler

        return decorator

    # --- регистрация middleware ---
    def _add_message_middleware(self, middleware):
        """Добавить middleware для message-хэндлеров."""
        self._middlewares["message"].append(middleware)
        return middleware

    def _add_callback_middleware(self, middleware):
        """Добавить middleware для callback-хэндлеров."""
        self._middlewares["callback_query"].append(middleware)
        return middleware

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

class _FakeHandlerRegistry:
    """Имитация router.message / router.callback_query из aiogram."""
    def __init__(self, registry_list, middleware_list):
        self._registry = registry_list
        self._middlewares = middleware_list

    def __call__(self, *filters, **kwargs):
        """Позволяет использовать @router.message(...) как декоратор."""
        def decorator(handler):
            self._registry.append((filters, handler))
            return handler
        return decorator

    def register(self, *filters, **kwargs):
        """Позволяет использовать router.message.register(...)"""
        def decorator(handler):
            self._registry.append((filters, handler))
            return handler
        return decorator

    def middleware(self, middleware):
        """Позволяет router.message.middleware(...)"""
        self._middlewares.append(middleware)
        return middleware

# --- Bot / Dispatcher / keyboard classes ---
class FakeBot:
    def __init__(self):
        self.sent = []

        # для тестирования изменений сообщения
        self.calls = []
        self.edit_media_behavior = None
        self.edit_text_behavior = None
        self.delete_behavior = None

    async def me(self):
        return SimpleNamespace(username="username bot")

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=text)

    async def send_photo(self, chat_id, photo, caption="", **kwargs):
        self.sent.append((chat_id, caption, photo))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=caption, photo=[SimpleNamespace(file_id='1')])

    async def send_document(self, chat_id, document, caption="", **kwargs):
        self.sent.append((chat_id, caption, document))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=caption, document=SimpleNamespace(file_id='1'))

    def clear(self):
        self.sent.clear()
        self.calls.clear()
        self.edit_media_behavior = None
        self.edit_text_behavior = None
        self.delete_behavior = None

    def get_edited_message(self, user_id: int, message_id: int, message: str):
        return any(user_id == chat_id and message == text and received_message_id == message_id
                   for func_name, chat_id, received_message_id, text, reply_markup in self.calls)

    def get_message(self, chat_id: int, text: str) -> bool:
        return any(c == chat_id and t == text for c, t, _ in self.sent)

    def check_str_in_messages(self, text: str):
        return any(text in t for _, t, _ in self.sent)

    def check_str_in_edited_messages(self, text: str):
        return any(text in text for _, _, _, text, _ in self.calls)

    # дял тестирования изменений сообщения
    async def edit_message_media(self, chat_id, message_id, media, caption="", reply_markup=None):
        self.calls.append(("edit_message_media", chat_id, message_id, caption, reply_markup))
        if callable(self.edit_media_behavior):
            return await self.edit_media_behavior(chat_id=chat_id, message_id=message_id, media=media,reply_markup=reply_markup)
        if isinstance(self.edit_media_behavior, BaseException):
            raise self.edit_media_behavior
        # стандартный успешный ответ: возвращаем объект с photo -> last .file_id
        return SimpleNamespace(photo=[SimpleNamespace(file_id="new_file_id")])

    async def edit_message_text(self, text, chat_id, message_id, parse_mode=None, reply_markup=None):
        self.calls.append(("edit_message_text", chat_id, message_id, text, reply_markup))
        if callable(self.edit_text_behavior):
            return await self.edit_text_behavior(chat_id=chat_id, message_id=message_id, text=text,
                                                 reply_markup=reply_markup)
        if isinstance(self.edit_text_behavior, BaseException):
            raise self.edit_text_behavior
        return SimpleNamespace(text=text)

    async def delete_message(self, chat_id, message_id):
        self.calls.append(("delete_message", chat_id, message_id, '', ''))
        if callable(self.delete_behavior):
            return await self.delete_behavior(chat_id=chat_id, message_id=message_id)
        if isinstance(self.delete_behavior, BaseException):
            raise self.delete_behavior
        return True

# шпион для send_message (будет мокаем вместо реальной функции)
class SpySend:
    def __init__(self):
        self.calls = []

    async def __call__(self, chat_id, message, image_key=None, fallback_image_key=None, reply_markup=None, parse_mode=None):
        self.calls.append((chat_id, message, image_key, reply_markup))
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), text=message)


class FakeDispatcher:
    pass

class FakeInlineKeyboardButton:
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


class FakeReplyKeyboardBuilder:
    def __init__(self):
        self._buttons = []

    def add(self, *buttons):
        self._buttons.extend(buttons)

    def adjust(self, *a, **kw):
        pass

    def as_markup(self, **kw):
        return self._buttons

    def row(self,  *buttons, width: int | None = None):
        pass


class FakeInlineKeyboardBuilder:
    def __init__(self):
        self._buttons = []

    def add(self, *buttons):
        self._buttons.extend(buttons)

    def adjust(self, *a, **kw):
        pass

    def as_markup(self):
        return self._buttons

    def row(self,  *buttons, width: int | None = None):
        pass

# --- BaseMiddleware (эмуляция aiogram.BaseMiddleware) ---
class BaseMiddleware:
    """Базовый класс мидлвари, аналогичный aiogram.BaseMiddleware."""
    def __init__(self):
        pass

    async def __call__(self, handler, event, data):
        """По умолчанию просто вызывает следующий обработчик."""
        return await handler(event, data)


class FakeTelegramForbiddenError(Exception):
    message="error"

class FakeTelegramBadRequest(Exception):
    message="error"

class FakeTelegramNotFound(Exception):
    message="error"

class FakeTelegramRetryAfter(Exception):
    message="error"


class FakeFSInputFile:
    """
    Фейковая замена aiogram.types.FSInputFile.
    Просто хранит путь до файла и имя, не открывает его.
    """
    def __init__(self, path: str, filename: str | None = None):
        self.path = path
        self.filename = filename or path.split("/")[-1] if filename else None

    def read(self):
        return b"fake-bytes"

    def __repr__(self):
        return f"<FakeFSInputFile path='{self.path}' filename='{self.filename}'>"


class FakeInputMediaPhoto:
    """
    Фейковая замена aiogram.types.InputMediaPhoto.
    Используется для edit_message_media / send_media_group и т.п.
    """
    def __init__(self, media: str | FakeFSInputFile, caption: str | None = None, **kwargs):
        self.media = media  # может быть строка (file_id, URL) или FSInputFile
        self.caption = caption
        self.kwargs = kwargs

    def __repr__(self):
        return f"<FakeInputMediaPhoto media={self.media} caption={self.caption}>"
