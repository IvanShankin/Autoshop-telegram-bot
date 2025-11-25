from aiogram import Router

from src.modules.admin_actions.handlers.editor.category.create_handlers import router as router_create
from src.modules.admin_actions.handlers.editor.category.delete_handlers import router as router_delete
from src.modules.admin_actions.handlers.editor.category.import_handlers import router as router_import
from src.modules.admin_actions.handlers.editor.category.show_handlers import router as router_show
from src.modules.admin_actions.handlers.editor.category.update_handlers import router as router_update

router = Router()
router.include_router(router_create)
router.include_router(router_delete)
router.include_router(router_import)
router.include_router(router_show)
router.include_router(router_update)

__all__ = [
    'router'
]