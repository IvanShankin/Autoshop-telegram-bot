import asyncio

from src.infrastructure.rebbit_mq._consumer import start_background_consumer, stop_background_consumer
from src.deferred_tasks.core import init_scheduler
from src.services.database.backups.backup_db import add_backup_create, add_backup_cleanup
from src.services.database.core.filling_database import create_database
from src.services.fastapi_core.server import start_server
from src.infrastructure.redis import init_redis, close_redis
from src.services.redis.filling import filling_all_redis
from src.services.database.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
from src.infrastructure.telegram.bot_run import run_bot
from src.services.redis.tasks import start_dollar_rate_scheduler
from src.services.secrets import init_crypto_context
from src.config import get_config, init_config
from src.utils.core_logger import setup_logging


async def start_app():
    """
    Асинхронный контекстный менеджер для запуска приложения.
    Инициализирует конфиг, Redis, Database, запуск отложенных задач.
    """
    init_config()  # конфиги необходимо до init_crypto_context
    await init_redis()

    try:
        init_crypto_context()
    except RuntimeError as e: # если уже есть
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

    try:
        await run_bot()
    finally:
        await stop_background_consumer()
        await close_redis()