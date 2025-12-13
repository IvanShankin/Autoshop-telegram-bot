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

from src.modules.admin_actions.handlers.editor.promo_codes.create_handlers import router as create_promo_codes_router
from src.modules.admin_actions.handlers.editor.promo_codes.show_handlers import router as show_promo_codes_router
from src.modules.admin_actions.handlers.editor.promo_codes.delete_handlers import router as delete_promo_codes_router

from src.modules.admin_actions.handlers.editor.mass_mailing.editor_handlers import router as editor_mass_mailing_router
from src.modules.admin_actions.handlers.editor.mass_mailing.show_handlers import router as show_mass_mailing_router

from src.modules.admin_actions.handlers.settings.main_settings_handlers import router as main_settings_router
from src.modules.admin_actions.handlers.settings.main_settings_handlers import router_logger as logger_router
from src.modules.admin_actions.handlers.settings.change_settings_handlers import router as change_settings_router
from src.modules.admin_actions.handlers.settings.change_admins_handlers import router as change_admins_router

from src.modules.admin_actions.handlers.show_data_by_id import router as show_data_by_id_router


router = Router()
router_logger = Router()

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

router.include_router(create_promo_codes_router)
router.include_router(show_promo_codes_router)
router.include_router(delete_promo_codes_router)

router.include_router(editor_mass_mailing_router)
router.include_router(show_mass_mailing_router)

router.include_router(main_settings_router)
router.include_router(change_settings_router)
router.include_router(change_admins_router)

router.include_router(show_data_by_id_router)

router_logger.include_router(logger_router)

__all__ = [
    'router',
    'router_logger',
    'router_with_repl_kb',
]