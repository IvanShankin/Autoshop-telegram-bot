import asyncio

from src.containers.app_container import AppContainer
from src.infrastructure.crypto_bot.core import init_crypto_provider
from src.infrastructure.rabbit_mq._consumer import start_background_consumer, stop_background_consumer
from src.deferred_tasks.core import init_scheduler
from src.services._database.backups.backup_db import add_backup_create, add_backup_cleanup
from src.services._database.core.filling_database import create_database
from src.services.fastapi_core.server import start_server
from src.infrastructure.redis import init_redis, close_redis
from src.services._redis.filling import filling_all_redis
from src.services._database.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
from src.infrastructure.telegram.bot_run import run_bot
from src.services._redis.tasks import start_dollar_rate_scheduler
from src.services.secrets import init_crypto_context
from src.config import get_config, init_config
from src.utils.core_logger import setup_logging


async def start_app():
    """
    Асинхронный контекстный менеджер для запуска приложения.
    Инициализирует конфиг, Redis, Database, запуск отложенных задач.
    """

    app_container = AppContainer()
    async_session_factory = app_container.conf.db_connection.session_local

    await create_database()

    # заполнение кэша
    async with async_session_factory() as session:
        request_container = app_container.get_request_container(session)

        warmup = request_container.get_cache_warmup_service()
        await warmup.warmup()

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
        await run_bot(app_container)
    finally:
        await app_container.shutdown()