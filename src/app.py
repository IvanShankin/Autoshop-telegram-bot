import asyncio

from src.containers.app_container import AppContainer
from src.application.deferred_tasks.creator_works import InitScheduler
from src.infrastructure.scheduler.core import init_scheduler
from src.infrastructure.web.server import start_server
from src.infrastructure.telegram.bot_run import run_bot


async def start_app():
    """
    Асинхронный контекстный менеджер для запуска приложения.
    Инициализирует конфиг, Redis, Database, запуск отложенных задач.
    """

    app_container = AppContainer()
    async_session_factory = app_container.conf.db_connection.session_local

    # заполнение кэша
    async with async_session_factory() as session:
        request_container = app_container.get_request_container(session)

        warmup = request_container.get_cache_warmup_service()
        await warmup.warmup()

    # отложенный задачник
    scheduler = init_scheduler()
    InitScheduler(scheduler=scheduler, container_factory=app_container.get_request_container_factory())

    asyncio.create_task(start_server(app_container)) # FastAPI

    backup_db = request_container.get_backup_db()
    backup_db.add_backup_create(scheduler)
    backup_db.add_backup_cleanup(scheduler)

    scheduler.start()

    await app_container.start()

    try:
        await run_bot(app_container)
    except KeyboardInterrupt:
        app_container.logger.info("Приложение завершило работу")
    finally:
        await app_container.shutdown()