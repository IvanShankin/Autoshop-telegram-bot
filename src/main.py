import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from src.database.filling_database import create_database
from src.middlewares.database import DataBaseSessionMiddleware

load_dotenv()
TOKEN_BOT = os.getenv('TOKEN_BOT')

bot = Bot(token=TOKEN_BOT)
dp = Dispatcher() # диспетчер выполняющий работу роутера
dp.message.middleware(DataBaseSessionMiddleware())

async def main():
    await create_database()
    # dp.include_router(router)
    # await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        print("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот завершил работу")