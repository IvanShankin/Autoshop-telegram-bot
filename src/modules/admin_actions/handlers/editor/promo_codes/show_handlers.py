from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import admin_promo_kb, all_admin_promo_kb, \
    back_in_all_admin_promo_kb, show_admin_promo_kb

from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "admin_promo")
async def admin_promo(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await state.clear()
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=admin_promo_kb(user.language)
    )


@router.callback_query(F.data.startswith("admin_promo_list:"))
async def admin_promo_list(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    show_not_valid = bool(int(callback.data.split(":")[1]))
    current_page = int(callback.data.split(":")[2])

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        event_message_key='admin_panel',
        reply_markup=await all_admin_promo_kb(
            current_page=current_page,
            language=user.language,
            show_not_valid=show_not_valid,
            admin_module=admin_module,
        )
    )


@router.callback_query(F.data.startswith("show_admin_promo:"))
async def show_admin_promo(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    current_page = int(callback.data.split(':')[1])
    show_not_valid = bool(int(callback.data.split(":")[2]))
    promo_code_id = int(callback.data.split(":")[3])

    promo_code = await admin_module.promo_code_service.get_promo_code(promo_code_id=promo_code_id, get_only_valid=False)

    if not promo_code:
        text = get_text(user.language, "admins_editor_promo_codes", "promo_code_not_found")
        reply_markup = back_in_all_admin_promo_kb(user.language, current_page, show_not_valid)
    else:
        text = get_text(
            user.language,
            "admins_editor_promo_codes",
            "promo_code_details"
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
                start_at=promo_code.start_at.strftime(admin_module.conf.different.dt_format),
                expire_at=(promo_code.expire_at.strftime(admin_module.conf.different.dt_format) if promo_code.expire_at else
                           get_text(user.language, "admins_editor_promo_codes", "endlessly"))
            )
        reply_markup = show_admin_promo_kb(
            language=user.language,
            current_page=current_page,
            promo_code_id=promo_code_id,
            show_not_valid=show_not_valid,
            is_valid=promo_code.is_valid
        )

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='admin_panel',
        reply_markup=reply_markup
    )


