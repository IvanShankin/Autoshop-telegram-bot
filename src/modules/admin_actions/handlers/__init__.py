from aiogram import Router

from src.modules.admin_actions.handlers.main_handlers import router as main_router, router_with_repl_kb
from src.modules.admin_actions.handlers.editor.category import router as editor_categories_router
from src.modules.admin_actions.handlers.editor.service import router as editor_service_router

from src.modules.admin_actions.handlers.user_management.management_show import router as show_handler_router
from src.modules.admin_actions.handlers.user_management.management_update import router as management_update_router
from src.modules.admin_actions.handlers.user_management.management_upload import router as management_upload_router

from src.modules.admin_actions.handlers.editor.navigator_handler import router as navigator_router
from src.modules.admin_actions.handlers.editor.replenishments.replenishment_handlers import router as replenishment_router
from src.modules.admin_actions.handlers.editor.images.images_handles import router as image_router
from src.modules.admin_actions.handlers.editor.ref_system.ref_system_handlers import router as ref_system_router
from src.modules.admin_actions.handlers.editor.vouchers.create_handlers import router as create_vouchers_router
from src.modules.admin_actions.handlers.editor.vouchers.show_handlers import router as show_vouchers_router
from src.modules.admin_actions.handlers.editor.vouchers.delete_handlers import router as delete_vouchers_router

router = Router()
router.include_router(main_router)
router.include_router(editor_categories_router)
router.include_router(editor_service_router)
router.include_router(show_handler_router)
router.include_router(management_update_router)
router.include_router(management_upload_router)
router.include_router(navigator_router)
router.include_router(replenishment_router)
router.include_router(image_router)
router.include_router(ref_system_router)
router.include_router(create_vouchers_router)
router.include_router(show_vouchers_router)
router.include_router(delete_vouchers_router)

__all__ = [
    'router',
    'router_with_repl_kb',
]