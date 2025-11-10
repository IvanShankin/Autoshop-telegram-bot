from aiogram import Bot, Dispatcher

from src.config import TOKEN_BOT, TOKEN_LOGGER_BOT
from src.services.database.system.actions import get_settings
from src.utils.secret_data import decrypt_data

_bot = Bot(token=TOKEN_BOT)
_dp = Dispatcher()

_bot_logger = Bot(token=TOKEN_LOGGER_BOT)
_dp_logger = Dispatcher()

async def get_bot() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global _bot
    return _bot

async def get_dispatcher() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    global _bot
    return _dp

async def get_bot_logger() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global _bot_logger
    return _bot_logger

async def get_dispatcher_logger() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    global _dp_logger
    return _dp_logger
