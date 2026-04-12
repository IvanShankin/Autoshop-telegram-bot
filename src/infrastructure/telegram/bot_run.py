import asyncio

from src.containers.app_container import AppContainer
from src.exceptions.business import ForbiddenError
from src.infrastructure.telegram.bot_instance import get_dispatcher, get_dispatcher_logger, get_bot, get_bot_logger
from src.middlewares.aiogram_middleware import MaintenanceMiddleware, UserMiddleware, OnlyAdminsMiddleware, \
    DeleteMessageOnErrorMiddleware, CheckuserNotBlok, ModulesMiddleware
from src.modules.profile.handlers import router_with_repl_kb as profile_router_with_repl_kb, router as profile_router
from src.modules.categories.handlers import router_with_repl_kb as catalog_router_with_repl_kb
from src.modules.categories.handlers import router as catalog_router
from src.modules.start_handler import router as start_router
from src.modules.info_handler import router_with_repl_kb as info_router_router_with_repl_kb
from src.modules.admin_actions.handlers import router as admin_router
from src.modules.admin_actions.handlers import router_with_repl_kb as admin_router_with_repl_kb
from src.modules.admin_actions.handlers import router_logger


async def _including_router(app_container: AppContainer):
    dp = get_dispatcher()
    dp_logger = get_dispatcher_logger()

    dp.update.middleware(CheckuserNotBlok())
    dp.update.middleware(DeleteMessageOnErrorMiddleware(ForbiddenError, "Insufficient rights"))
    dp_logger.update.middleware(DeleteMessageOnErrorMiddleware(ForbiddenError, "Insufficient rights"))

    dp.include_router(start_router)
    dp.include_router(info_router_router_with_repl_kb)
    dp.include_router(catalog_router_with_repl_kb)
    dp.include_router(catalog_router)
    dp.include_router(profile_router_with_repl_kb)
    dp.include_router(profile_router)
    dp.include_router(admin_router)
    dp.include_router(admin_router_with_repl_kb)

    # роутер только для админов
    admin_router.message.middleware(OnlyAdminsMiddleware())
    admin_router.callback_query.middleware(OnlyAdminsMiddleware())

    admin_router_with_repl_kb.message.middleware(OnlyAdminsMiddleware())
    admin_router_with_repl_kb.callback_query.middleware(OnlyAdminsMiddleware())

    dp.update.middleware(ModulesMiddleware(app_container))

    dp.update.middleware(UserMiddleware()) # использует ModulesMiddleware
    dp.update.middleware(MaintenanceMiddleware())

    dp_logger.include_router(router_logger)
    dp_logger.update.middleware(UserMiddleware())


async def run_bot(app_container: AppContainer):
    """Запуск бота, вызывается отдельно из main.py"""
    bot = get_bot()
    bot_logger = get_bot_logger()

    dp = get_dispatcher()
    dp_logger = get_dispatcher_logger()

    await _including_router(app_container)

    await asyncio.gather(
        dp.start_polling(bot),
        dp_logger.start_polling(bot_logger),
    )