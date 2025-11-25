from aiogram import Router

from src.modules.admin_actions.handlers.editor.service.editor_services_handlers import router as main_router

router = Router()
router.include_router(main_router)

__all__ = [
    'router'
]