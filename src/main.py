import asyncio

from src.services.database.events.core_event import event_queue
from src.services.database.events.triggers_processing import run_triggers_processing
from src.services.database.filling_database import create_database
from src.redis_dependencies.filling_redis import filling_all_redis
from src.services.discounts.actions import deactivate_expired_promo_codes_and_vouchers


async def main():
    await create_database()
    await filling_all_redis()
    asyncio.create_task(run_triggers_processing())
    asyncio.create_task(deactivate_expired_promo_codes_and_vouchers())
    await event_queue.join() # ОБЯЗАТЕЛЬНО ДОЖДАТЬСЯ ВЫПОЛНЕНИЕ СОБЫТИЙ

if __name__ == '__main__':
    try:
        print("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот завершил работу")