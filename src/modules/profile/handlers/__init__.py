from aiogram import Router

from src.modules.profile.handlers.main_handlers import router as main_router, router_with_repl_kb
from src.modules.profile.handlers.accounts_handlers import router as account_router
from src.modules.profile.handlers.settings_handlers import router as settings_router
from src.modules.profile.handlers.history_trans_handlers import router as history_router
from src.modules.profile.handlers.ref_system_handlers import router as ref_system_router
from src.modules.profile.handlers.transfer_balance_handler import router as transfer_balance_router
from src.modules.profile.handlers.replenishment_handler import router as money_replenishment_router


router = Router()
router.include_router(main_router)
router.include_router(settings_router)
router.include_router(account_router)
router.include_router(history_router)
router.include_router(ref_system_router)
router.include_router(transfer_balance_router)
router.include_router(money_replenishment_router)

__all__ = [
    'router',
    'router_with_repl_kb',
]