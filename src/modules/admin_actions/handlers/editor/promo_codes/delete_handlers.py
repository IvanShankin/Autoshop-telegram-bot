from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import back_in_all_admin_promo_kb, confirm_deactivate_promo_code_kb

from src.utils.i18n import get_text


router = Router()


@router.callback_query(F.data.startswith("confirm_deactivate_promo_code:"))
async def confirm_deactivate_promo_code(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    promo_code_id = int(callback.data.split(":")[1])
    show_not_valid = bool(int(callback.data.split(":")[2]))
    current_page = int(callback.data.split(':')[3])

    promo_code = await admin_module.promo_code_service.get_promo_code(promo_code_id=promo_code_id)

    if not promo_code:
        text = get_text(user.language, "admins_editor_promo_codes", "promo_code_not_found")
        reply_markup = back_in_all_admin_promo_kb(user.language, current_page, show_not_valid)
    else:
        text = get_text(
            user.language,
            "admins_editor_promo_codes",
            "confirmation_delete_promo_code"
        )
        reply_markup = confirm_deactivate_promo_code_kb(user.language, current_page, promo_code_id, show_not_valid)

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("deactivate_promo_code:"))
async def deactivate_promo_code_handler(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    promo_code_id = int(callback.data.split(":")[1])
    show_not_valid = bool(int(callback.data.split(":")[2]))
    current_page = int(callback.data.split(':')[3])

    promo_code = await admin_module.promo_code_service.get_promo_code(promo_code_id=promo_code_id, get_only_valid=False)

    if not promo_code or not promo_code.is_valid:
        text = get_text(user.language, "admins_editor_promo_codes", "promo_code_already_deactivated")
    else:
        await admin_module.promo_code_service.deactivate_promo_code(user.user_id, promo_code_id)
        text = get_text(user.language, "admins_editor_promo_codes", "promo_code_successfully_deactivated")


    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        reply_markup=back_in_all_admin_promo_kb(user.language, current_page, show_not_valid)
    )