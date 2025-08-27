import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from srс.handlers import router

load_dotenv()
TOKEN_BOT = os.getenv('TOKEN_BOT')

bot = Bot(token=TOKEN_BOT)
dp = Dispatcher() # диспетчер выполняющий работу роутера

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        print("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот завершил работу")