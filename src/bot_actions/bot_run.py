from src.middlewares.aiogram_middleware import MaintenanceMiddleware
from src.modules.profile.handlers import router_with_repl_kb as profile_router_with_repl_kb, router as profile_router
from src.modules.catalog import router_with_repl_kb as catalog_router_with_repl_kb
from src.modules.catalog import router as catalog_router
from src.modules.start_handler import router as start_router
from src.bot_actions.bot_instance import get_bot, get_dispatcher


async def _including_router():
    dp = await get_dispatcher()

    start_router.message.middleware(MaintenanceMiddleware(allow_admins=True))
    dp.include_router(start_router)

    catalog_router_with_repl_kb.message.middleware(MaintenanceMiddleware())
    dp.include_router(catalog_router_with_repl_kb)

    catalog_router.message.middleware(MaintenanceMiddleware())
    dp.include_router(catalog_router)

    profile_router_with_repl_kb.message.middleware(MaintenanceMiddleware())
    dp.include_router(profile_router_with_repl_kb)

    profile_router.message.middleware(MaintenanceMiddleware())
    dp.include_router(profile_router)


async def run_bot():
    """Запуск бота, вызывается отдельно из main.py"""
    bot = await get_bot()
    dp = await get_dispatcher()

    await _including_router()
    await dp.start_polling(bot)