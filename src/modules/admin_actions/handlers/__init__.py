from aiogram import Router

from src.modules.admin_actions.handlers.main_handlers import router as main_router, router_with_repl_kb
from src.modules.admin_actions.handlers.editor.category import router as editor_categories_router
from src.modules.admin_actions.handlers.editor.service import router as editor_service_router

router = Router()
router.include_router(main_router)
router.include_router(editor_categories_router)
router.include_router(editor_service_router)

__all__ = [
    'router',
    'router_with_repl_kb',
]