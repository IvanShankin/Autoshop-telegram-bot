from typing import Optional

from aiogram import Bot, Dispatcher

from src.config import get_config

_bot: Optional[Bot] = None
_dp = Dispatcher()

_bot_logger: Optional[Bot] = None
_dp_logger = Dispatcher()



async def get_bot() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global _bot
    if _bot is None:
        _bot = Bot(token=get_config().secrets.token_bot)

    return _bot


async def get_dispatcher() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    global _bot
    return _dp


async def get_bot_logger() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global _bot_logger
    if _bot_logger is None:
        _bot_logger = Bot(token=get_config().secrets.token_logger_bot)
    return _bot_logger


async def get_dispatcher_logger() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    global _dp_logger
    return _dp_logger
