from aiogram import Bot, Dispatcher

from src.middlewares.database import DataBaseSessionMiddleware
from src.config import TOKEN_BOT
from src.services.system.actions import get_settings
from src.utils.secret_data import decrypt_token

bot: Bot | None = None
dp: Dispatcher | None = None

bot_logger: Bot | None = None
dp_logger: Dispatcher | None = None

async def get_bot() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global bot, dp
    if bot is None or dp is None:
        bot = Bot(token=TOKEN_BOT)
        dp = Dispatcher()
        dp.message.middleware(DataBaseSessionMiddleware())
    return bot

async def get_dispatcher() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    if dp is None:
        await get_bot()
    return dp

async def get_bot_logger() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global bot, dp
    if bot is None or dp is None:
        settings = await get_settings()
        bot = Bot(token=decrypt_token(settings.hash_token_logger_bot)) # расшифровываем токен
        dp = Dispatcher()
        dp.message.middleware(DataBaseSessionMiddleware())
    return bot

async def get_dispatcher_logger() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    if dp is None:
        await get_bot_logger()
    return dp
