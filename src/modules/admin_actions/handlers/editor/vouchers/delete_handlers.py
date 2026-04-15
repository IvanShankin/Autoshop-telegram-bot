from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import back_in_all_admin_voucher_kb, confirm_deactivate_admin_voucher_kb

from src.utils.i18n import get_text


router = Router()


@router.callback_query(F.data.startswith("confirm_deactivate_admin_voucher:"))
async def confirm_deactivate_admin_voucher(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await admin_module.voucher_service.get_voucher_by_id(voucher_id)

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
        reply_markup = back_in_all_admin_voucher_kb(user.language, current_page)
        image_key = 'admin_panel'
    else:
        text = get_text(
            user.language,
            "admins_editor_vouchers",
            "confirmation_delete_voucher"
        )
        image_key = None
        reply_markup = confirm_deactivate_admin_voucher_kb(user.language, current_page, voucher_id, voucher.is_valid)

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key=image_key,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("deactivate_admin_voucher:"))
async def deactivate_admin_voucher(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages
):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await admin_module.voucher_service.get_voucher_by_id(voucher_id)

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
    else:
        await admin_module.voucher_service.deactivate_voucher(voucher_id)
        text = get_text(user.language, "admins_editor_vouchers", "voucher_successfully_deleted")


    await messages_service.edit_msg.edit(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=text,
            reply_markup=back_in_all_admin_voucher_kb(user.language, current_page)
    )