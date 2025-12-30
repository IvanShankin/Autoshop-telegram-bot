import asyncio

from src.broker.consumer import start_background_consumer, stop_background_consumer
from src.services.database.core.filling_database import create_database
from src.services.fastapi_core.server import start_server
from src.services.redis.filling_redis import filling_all_redis
from src.services.database.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
from src.bot_actions.bot_run import run_bot
from src.services.redis.tasks import start_dollar_rate_scheduler
from src.services.secrets import init_crypto_context, get_crypto_context
from src.utils.core_logger import logger

async def on_startup():
    if not get_crypto_context():
        init_crypto_context()

    await create_database()
    await filling_all_redis()
    await start_background_consumer()

    asyncio.create_task(deactivate_expired_promo_codes_and_vouchers())
    asyncio.create_task(start_dollar_rate_scheduler())
    asyncio.create_task(start_server())

    await run_bot()

async def on_shutdown():
    # аккуратно остановим consumer
    await stop_background_consumer()

if __name__ == '__main__':
    try:
        logger.info("Бот начал работу")
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        logger.info("Бот завершил работу")
    except Exception as e:
        logger.exception(f"ошибка: {e}")
    finally:
        asyncio.run(on_shutdown())