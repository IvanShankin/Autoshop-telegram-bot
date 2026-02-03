import sys
from types import ModuleType
import pytest
from tests.helpers.fake_aiogram.fake_aiogram_module import (
    _FakeAttr, FakeMessage, FakeCallbackQuery, FakeFSMContext,
    FakeRouter, FakeBot, FakeDispatcher,
    FakeInlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply, FakeInlineKeyboardBuilder,
    BaseMiddleware, FakeTelegramForbiddenError, FakeTelegramBadRequest, FakeInputMediaPhoto, FakeFSInputFile,
    FakeBaseFilter, FakeState, FakeStatesGroup, FakeCommandObject, FakeTelegramObject, FakeReplyKeyboardBuilder,
    FakeDocument, FakeBufferedInputFile, FakeTelegramNotFound, FakeTelegramRetryAfter, FakeCommand, FakeStateFilter,
    FakeTelegramAPIError, FakeReactionTypeEmoji
)

@pytest.fixture(scope="session")
def patch_fake_aiogram():
    """
    Регистрирует фейковый aiogram в sys.modules (scope=session).
    По умолчанию не autouse — подключай в тесте аргументом или
    ставь autouse=True если хочешь глобальную подмену.
    """
    # сохранить и удалить реальные aiogram-модули (если есть)
    saved = {}
    for name in list(sys.modules):
        if name == "aiogram" or name.startswith("aiogram."):
            saved[name] = sys.modules.pop(name)

    fake = ModuleType("aiogram")

    # register root attributes
    fake.F = _FakeAttr()
    fake.Router = FakeRouter
    fake.Bot = FakeBot
    fake.Dispatcher = FakeDispatcher
    fake.BaseMiddleware = BaseMiddleware

    # create submodules
    sys.modules["aiogram"] = fake
    sys.modules["aiogram.filters"] = ModuleType("aiogram.filters")
    sys.modules["aiogram.filters"].CommandStart = object
    sys.modules["aiogram.filters"].Text = object
    sys.modules["aiogram.filters"].BaseFilter = FakeBaseFilter
    sys.modules["aiogram.filters"].Command = FakeCommand
    sys.modules["aiogram.filters"].CommandObject = FakeCommandObject
    sys.modules["aiogram.filters"].StateFilter = FakeStateFilter
    sys.modules["aiogram.filters.state"] = ModuleType("aiogram.filters.state")
    sys.modules["aiogram.filters.state"].StateFilter = object

    sys.modules["aiogram.types"] = ModuleType("aiogram.types")
    sys.modules["aiogram.types"].Message = FakeMessage
    sys.modules["aiogram.types"].CallbackQuery = FakeCallbackQuery
    sys.modules["aiogram.types"].InlineKeyboardButton = FakeInlineKeyboardButton
    sys.modules["aiogram.types"].InlineKeyboardMarkup = InlineKeyboardMarkup
    sys.modules["aiogram.types"].KeyboardButton = KeyboardButton
    sys.modules["aiogram.types"].ReplyKeyboardMarkup = ReplyKeyboardMarkup
    sys.modules["aiogram.types"].ReplyKeyboardRemove = ReplyKeyboardRemove
    sys.modules["aiogram.types"].ForceReply = ForceReply
    sys.modules["aiogram.types"].FSInputFile = FakeFSInputFile
    sys.modules["aiogram.types"].InputMediaPhoto = FakeInputMediaPhoto
    sys.modules["aiogram.types"].TelegramObject = FakeTelegramObject
    sys.modules["aiogram.types"].Document = FakeDocument
    sys.modules["aiogram.types"].BufferedInputFile = FakeBufferedInputFile
    sys.modules["aiogram.types"].ReactionTypeEmoji = FakeReactionTypeEmoji

    sys.modules["aiogram.utils"] = ModuleType("aiogram.utils")
    sys.modules["aiogram.utils.keyboard"] = ModuleType("aiogram.utils.keyboard")
    sys.modules["aiogram.utils.keyboard"].InlineKeyboardBuilder = FakeInlineKeyboardBuilder
    sys.modules["aiogram.utils.keyboard"].ReplyKeyboardBuilder = FakeReplyKeyboardBuilder

    sys.modules["aiogram.fsm"] = ModuleType("aiogram.fsm")
    sys.modules["aiogram.fsm.context"] = ModuleType("aiogram.fsm.context")
    sys.modules["aiogram.fsm.context"].FSMContext = FakeFSMContext
    sys.modules["aiogram.fsm.state"] = ModuleType("aiogram.fsm.state")
    sys.modules["aiogram.fsm.state"].StatesGroup = FakeStatesGroup
    sys.modules["aiogram.fsm.state"].State = FakeState

    sys.modules["aiogram.exceptions"] = ModuleType("aiogram.exceptions")
    sys.modules["aiogram.exceptions"].TelegramForbiddenError = FakeTelegramForbiddenError
    sys.modules["aiogram.exceptions"].TelegramAPIError = FakeTelegramAPIError
    sys.modules["aiogram.exceptions"].TelegramBadRequest = FakeTelegramBadRequest
    sys.modules["aiogram.exceptions"].TelegramNotFound = FakeTelegramNotFound
    sys.modules["aiogram.exceptions"].TelegramRetryAfter = FakeTelegramRetryAfter

    yield

    # cleanup: удалить всё, что мы добавили, и восстановить сохранённое
    for k in list(sys.modules):
        if k == "aiogram" or k.startswith("aiogram."):
            sys.modules.pop(k, None)
    for n, m in saved.items():
        sys.modules[n] = m
