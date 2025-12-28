from aiogram import Bot, Dispatcher

from src.bot_actions.throttler import RateLimiter
from src.config import TOKEN_BOT, TOKEN_LOGGER_BOT, RATE_SEND_MSG_LIMIT

_bot = Bot(token=TOKEN_BOT)
_dp = Dispatcher()

_bot_logger = Bot(token=TOKEN_LOGGER_BOT)
_dp_logger = Dispatcher()

GLOBAL_RATE_LIMITER = RateLimiter(max_calls=RATE_SEND_MSG_LIMIT, period=1.0)


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
