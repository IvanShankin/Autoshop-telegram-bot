from aiogram import Router

from src.modules.admin_actions.handlers.editor.event_msg.general import router as router_general
from src.modules.admin_actions.handlers.editor.event_msg.images import router as router_images
from src.modules.admin_actions.handlers.editor.event_msg.stickers import router as router_stickers

router = Router()
router.include_router(router_general)
router.include_router(router_images)
router.include_router(router_stickers)

__all__ = [
    'router'
]