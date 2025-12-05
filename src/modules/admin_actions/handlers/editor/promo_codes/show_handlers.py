from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.config import DT_FORMAT
from src.modules.admin_actions.keyboards.promo_codes_kb import admin_promo_kb, all_admin_promo_kb, \
    back_in_all_admin_promo_kb, show_admin_promo_kb
from src.services.database.discounts.actions import get_promo_code
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "admin_promo")
async def admin_promo(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=admin_promo_kb(user.language)
    )


@router.callback_query(F.data.startswith("admin_promo_list:"))
async def admin_promo_list(callback: CallbackQuery, user: Users):
    show_not_valid = bool(int(callback.data.split(":")[1]))
    current_page = int(callback.data.split(":")[2])

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='admin_panel',
        reply_markup=await all_admin_promo_kb(
            current_page=current_page,
            language=user.language,
            show_not_valid=show_not_valid
        )
    )


@router.callback_query(F.data.startswith("show_admin_promo:"))
async def show_admin_promo(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(':')[1])
    show_not_valid = bool(int(callback.data.split(":")[2]))
    promo_code_id = int(callback.data.split(":")[3])

    promo_code = await get_promo_code(promo_code_id=promo_code_id, get_only_valid=False)

    if not promo_code:
        text = get_text(user.language, 'admins_editor_promo_codes', "Promo code not found, please select another one")
        reply_markup = back_in_all_admin_promo_kb(user.language, current_page, show_not_valid)
    else:
        text = get_text(
            user.language,
            'admins_editor_promo_codes',
            "ID: {id} \n\n"
            "Valid: {valid} \n"
            "Code: {code} \n"
            "Minimum order amount: {min_order_amount} \n"
            "Discount amount: {amount} \n"
            "Discount percentage: {discount_percentage} \n"
            "Allowed number of activations: {number_of_activations} \n"
            "Number of activations: {activated_counter} \n"
            "Created: {start_at} \n"
            "Valid until: {expire_at}"
            ).format(
                id=promo_code_id,
                valid=promo_code.is_valid,
                code=promo_code.activation_code,
                min_order_amount=promo_code.min_order_amount,
                amount=promo_code.amount,
                discount_percentage=promo_code.discount_percentage,
                number_of_activations=(promo_code.number_of_activations if promo_code.number_of_activations else
                                        get_text(user.language, "admins_editor_promo_codes", "unlimited")),
                activated_counter=promo_code.activated_counter,
                start_at=promo_code.start_at.strftime(DT_FORMAT),
                expire_at=(promo_code.expire_at.strftime(DT_FORMAT) if promo_code.expire_at else
                           get_text(user.language, "admins_editor_promo_codes", "endlessly"))
            )
        reply_markup = show_admin_promo_kb(
            language=user.language,
            current_page=current_page,
            promo_code_id=promo_code_id,
            show_not_valid=show_not_valid,
            is_valid=promo_code.is_valid
        )

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='admin_panel',
        reply_markup=reply_markup
    )


