from aiogram import Bot, Dispatcher

from src.middlewares.database import DataBaseSessionMiddleware
from src.config import TOKEN_BOT
from src.services.system.actions import get_settings
from src.utils.secret_data import decrypt_token

_bot: Bot | None = None
_dp: Dispatcher | None = None

_bot_logger: Bot | None = None
_dp_logger: Dispatcher | None = None

async def get_bot() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global _bot, _dp
    if _bot is None or _dp is None:
        _bot = Bot(token=TOKEN_BOT)
        _dp = Dispatcher()
        _dp.message.middleware(DataBaseSessionMiddleware())
    return _bot

async def get_dispatcher() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    if _dp is None:
        await get_bot()
    return _dp

async def get_bot_logger() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global _bot, _dp
    if _bot is None or _dp is None:
        settings = await get_settings()
        _bot = Bot(token=decrypt_token(settings.hash_token_logger_bot)) # расшифровываем токен
        _dp = Dispatcher()
        _dp.message.middleware(DataBaseSessionMiddleware())
    return _bot

async def get_dispatcher_logger() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    if _dp is None:
        await get_bot_logger()
    return _dp
