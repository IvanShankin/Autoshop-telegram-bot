import asyncio

from src.containers.app_container import AppContainer
from src.deferred_tasks.core import init_scheduler
from src.application._database.backups.backup_db import add_backup_create, add_backup_cleanup
from src.application._database.core.filling_database import create_database
from src.application.fastapi_core.server import start_server
from src.application._database.discounts.utils.set_not_valid import deactivate_expired_promo_codes_and_vouchers
from src.infrastructure.telegram.bot_run import run_bot
from src.application._redis.tasks import start_dollar_rate_scheduler


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