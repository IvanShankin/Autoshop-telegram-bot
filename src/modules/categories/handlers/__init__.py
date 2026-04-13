from aiogram import Router

from src.modules.categories.handlers.handler_categories import router_with_repl_kb
from src.modules.categories.handlers.handler_categories import router as router_handler_catalog
from src.modules.categories.handlers.handler_promo_codes import router as promo_code_router

router = Router()
router.include_router(router_handler_catalog)
router.include_router(promo_code_router)

__all__ = [
    'router_with_repl_kb',
    'router',
]