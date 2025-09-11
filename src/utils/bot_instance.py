from aiogram import Bot, Dispatcher

from src.middlewares.database import DataBaseSessionMiddleware
from src.config import TOKEN_BOT

_bot: Bot | None = None
_dp: Dispatcher | None = None

def get_bot() -> Bot:
    """Возвращает глобальный объект Bot, создавая его при первом вызове"""
    global _bot, _dp
    if _bot is None or _dp is None:
        _bot = Bot(token=TOKEN_BOT)
        _dp = Dispatcher()
        _dp.message.middleware(DataBaseSessionMiddleware())
    return _bot

def get_dispatcher() -> Dispatcher:
    """Возвращает глобальный Dispatcher"""
    if _dp is None:
        get_bot()
    return _dp

async def run_bot():
    """Запуск бота, вызывается отдельно из main.py"""
    bot = get_bot()
    dp = get_dispatcher()
    await dp.start_polling(bot)