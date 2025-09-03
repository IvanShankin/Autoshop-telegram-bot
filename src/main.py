import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from src.database.events.core_event import event_queue
from src.database.events.triggers_processing import run_triggers_processing
from src.database.filling_database import create_database
from src.middlewares.database import DataBaseSessionMiddleware
from src.redis_dependencies.filling_redis import filling_all_redis

load_dotenv()
TOKEN_BOT = os.getenv('TOKEN_BOT')

bot = Bot(token=TOKEN_BOT)
dp = Dispatcher() # диспетчер выполняющий работу роутера
dp.message.middleware(DataBaseSessionMiddleware())

async def main():
    await create_database()
    await filling_all_redis()
    asyncio.create_task(run_triggers_processing())
    await event_queue.join() # ОБЯЗАТЕЛЬНО ДОЖДАТЬСЯ ВЫПОЛНЕНИЕ СОБЫТИЙ

if __name__ == '__main__':
    try:
        print("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот завершил работу")