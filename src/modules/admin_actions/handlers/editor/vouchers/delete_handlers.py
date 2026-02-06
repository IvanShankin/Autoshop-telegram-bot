from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.admin_actions.keyboards import back_in_all_admin_voucher_kb, confirm_deactivate_admin_voucher_kb
from src.services.database.discounts.actions import get_voucher_by_id, deactivate_voucher
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()


@router.callback_query(F.data.startswith("confirm_deactivate_admin_voucher:"))
async def confirm_deactivate_admin_voucher(callback: CallbackQuery, user: Users):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await get_voucher_by_id(voucher_id)

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

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key=image_key,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("deactivate_admin_voucher:"))
async def deactivate_admin_voucher(callback: CallbackQuery, user: Users):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await get_voucher_by_id(voucher_id)

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
    else:
        await deactivate_voucher(voucher_id)
        text = get_text(user.language, "admins_editor_vouchers", "voucher_successfully_deleted")


    await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=text,
            reply_markup=back_in_all_admin_voucher_kb(user.language, current_page)
    )