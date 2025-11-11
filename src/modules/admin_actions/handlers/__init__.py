from aiogram import Router

from src.modules.admin_actions.handlers.main_handlers import router as main_router, router_with_repl_kb

router = Router()
router.include_router(main_router)

__all__ = [
    'router',
    'router_with_repl_kb',
]