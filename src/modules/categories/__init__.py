from aiogram import Router

from src.modules.categories.handlers.handler_categories import router_with_repl_kb
from src.modules.categories.handlers.handler_categories import router as router_handler_catalog

router = Router()
router.include_router(router_handler_catalog)

__all__ = [
    'router_with_repl_kb',
    'router',
]