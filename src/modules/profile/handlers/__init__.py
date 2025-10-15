from aiogram import Router

from src.modules.profile.handlers.main_handlers import router as main_router, router_with_repl_kb
from src.modules.profile.handlers.settings_handlers import router as settings_router
from src.modules.profile.handlers.history_trans_handlers import router as history_router


router = Router()
router.include_router(main_router)
router.include_router(settings_router)
router.include_router(history_router)

__all__ = [
    'router',
    'router_with_repl_kb',
]