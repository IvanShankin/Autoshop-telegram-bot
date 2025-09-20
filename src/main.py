import asyncio

from src.services.database.filling_database import create_database
from src.redis_dependencies.filling_redis import filling_all_redis
from src.services.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers



async def main():
    await create_database()
    await filling_all_redis()
    asyncio.create_task(deactivate_expired_promo_codes_and_vouchers())

if __name__ == '__main__':
    try:
        print("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот завершил работу")