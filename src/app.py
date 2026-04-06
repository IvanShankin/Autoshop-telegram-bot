import asyncio

from src.infrastructure.crypto_bot.core import init_crypto_provider
from src.infrastructure.rabbit_mq._consumer import start_background_consumer, stop_background_consumer
from src.deferred_tasks.core import init_scheduler
from src.services._database.backups.backup_db import add_backup_create, add_backup_cleanup
from src.services._database.core.filling_database import create_database
from src.services.fastapi_core.server import start_server
from src.infrastructure.redis import init_redis, close_redis
from src.services.redis.filling import filling_all_redis
from src.services._database.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
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
    conf = init_config()
    await init_redis()
    init_crypto_provider(conf.secrets.token_crypto_bot)

    try:
        init_crypto_context() # необходим config
    except RuntimeError as e: # если уже есть
        pass

    setup_logging(conf.paths.log_file)
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