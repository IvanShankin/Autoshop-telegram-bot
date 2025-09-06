from src.config import TOKEN_BOT

bot = None
dp = None

async def run_bot():
    from aiogram import Bot, Dispatcher
    from src.middlewares.database import DataBaseSessionMiddleware

    bot = Bot(token=TOKEN_BOT)
    dp = Dispatcher()
    dp.message.middleware(DataBaseSessionMiddleware())
    await dp.start_polling(bot)
