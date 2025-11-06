from aiogram import Router

from src.modules.catalog.handler_catalog import router_with_repl_kb
from src.modules.catalog.selling_accounts import router as router_selling_accounts
from src.modules.catalog.handler_catalog import router as router_handler_catalog

router = Router()
router.include_router(router_selling_accounts)
router.include_router(router_handler_catalog)

__all__ = [
    'router_with_repl_kb',
    'router',
]