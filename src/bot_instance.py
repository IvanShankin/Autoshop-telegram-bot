from aiogram import Bot, Dispatcher

from src.middlewares.database import DataBaseSessionMiddleware
from src.config import TOKEN_BOT

bot: Bot = None
dp: Dispatcher = None

async def run_bot():

    bot = Bot(token=TOKEN_BOT)
    dp = Dispatcher()
    dp.message.middleware(DataBaseSessionMiddleware())
    await dp.start_polling(bot)
