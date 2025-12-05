from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.admin_actions.keyboards.promo_codes_kb import back_in_all_admin_promo_kb, \
    confirm_deactivate_promo_code_kb
from src.services.database.discounts.actions import get_promo_code
from src.services.database.discounts.actions.actions_promo import deactivate_promo_code
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()



@router.callback_query(F.data.startswith("confirm_deactivate_promo_code:"))
async def confirm_deactivate_promo_code(callback: CallbackQuery, user: Users):
    promo_code_id = int(callback.data.split(":")[1])
    show_not_valid = bool(int(callback.data.split(":")[2]))
    current_page = int(callback.data.split(':')[3])

    promo_code = await get_promo_code(promo_code_id=promo_code_id)

    if not promo_code:
        text = get_text(user.language, 'admins_editor_promo_codes', "Promo code not found, please select another one")
        reply_markup = back_in_all_admin_promo_kb(user.language, current_page, show_not_valid)
    else:
        text = get_text(
            user.language,
            'admins_editor_promo_codes',
            "Are you sure you want to delete this promo code?"
        )
        reply_markup = confirm_deactivate_promo_code_kb(user.language, current_page, promo_code_id, show_not_valid)

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("deactivate_promo_code:"))
async def deactivate_promo_code_handler(callback: CallbackQuery, user: Users):
    promo_code_id = int(callback.data.split(":")[1])
    show_not_valid = bool(int(callback.data.split(":")[2]))
    current_page = int(callback.data.split(':')[3])

    promo_code = await get_promo_code(promo_code_id=promo_code_id, get_only_valid=False)

    if not promo_code or not promo_code.is_valid:
        text = get_text(user.language, 'admins_editor_promo_codes', "This promo code has already been deactivated")
    else:
        await deactivate_promo_code(user.user_id, promo_code_id)
        text = get_text(user.language, 'admins_editor_promo_codes', "Promo code successfully deactivate")


    await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=text,
            reply_markup=back_in_all_admin_promo_kb(user.language, current_page, show_not_valid)
    )