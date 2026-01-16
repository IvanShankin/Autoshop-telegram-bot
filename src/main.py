import asyncio

from src.broker.consumer import start_background_consumer, stop_background_consumer
from src.deferred_tasks.core import init_scheduler
from src.services.database.backups.backup_db import add_backup_create, add_backup_cleanup
from src.services.database.core.filling_database import create_database
from src.services.fastapi_core.server import start_server
from src.services.redis.filling_redis import filling_all_redis
from src.services.database.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
from src.bot_actions.bot_run import run_bot
from src.services.redis.tasks import start_dollar_rate_scheduler
from src.services.secrets import init_crypto_context
from src.config import get_config, init_config
from src.utils.core_logger import setup_logging, get_logger


async def on_startup():
    init_config()  # конфиги необходимо до init_crypto_context

    try:
        init_crypto_context()
    except RuntimeError as e: # если уже есть
        print(f"\n\n{str(e)}\n\n")
        pass

    setup_logging(get_config().paths.log_file)
    await create_database()
    await filling_all_redis()
    await start_background_consumer()

    asyncio.create_task(deactivate_expired_promo_codes_and_vouchers())
    asyncio.create_task(start_dollar_rate_scheduler())
    asyncio.create_task(start_server())

    # отложенный задачник
    scheduler = init_scheduler()
    add_backup_create(scheduler)
    add_backup_cleanup(scheduler)
    scheduler.start()

    await run_bot()

async def on_shutdown():
    await stop_background_consumer()

if __name__ == '__main__':
    logger = get_logger(__name__)
    try:
        logger.info("Бот начал работу")
        asyncio.run(on_startup())
    except KeyboardInterrupt:
        logger.info("Бот завершил работу")
    except Exception as e:
        logger.exception(f"ошибка: {e}")
    finally:
        asyncio.run(on_shutdown())