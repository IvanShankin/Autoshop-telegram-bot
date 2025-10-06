import asyncio

from src.services.database.filling_database import create_database
from src.redis_dependencies.filling_redis import filling_all_redis
from src.services.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
from src.bot_actions.bot_run import run_bot
from src.utils.core_logger import logger

async def main():
    await create_database()
    await filling_all_redis()
    asyncio.create_task(deactivate_expired_promo_codes_and_vouchers())

    await run_bot()

if __name__ == '__main__':
    try:
        logger.info("Бот начал работу")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот завершил работу")
    except Exception as e:
        logger.exception(f"ошибка: {e}")