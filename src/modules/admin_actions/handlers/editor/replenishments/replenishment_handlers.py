from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards.editors.replenishment_kb import edit_type_payments_list_kb, edit_type_payment_kb, \
    back_in_edit_type_payment_kb
from src.modules.admin_actions.schemas import GetTypePaymentNameData, GetTypePaymentCommissionData
from src.modules.admin_actions.services import safe_get_type_payment
from src.modules.admin_actions.services import message_type_payment
from src.modules.admin_actions.state import GetTypePaymentName, GetTypePaymentCommission
from src.services.database.system.actions.actions import update_type_payment
from src.services.database.users.models import Users
from src.utils.converter import safe_float_conversion
from src.utils.i18n import get_text

router = Router()

async def show_type_payment(
    user: Users,
    type_payment_id: int,
    send_new_message: bool = False,
    message_id: int = None,
    callback: CallbackQuery = None
):
    type_payment = await safe_get_type_payment(type_payment_id=type_payment_id, user=user, callback=callback)
    if not type_payment:
        return

    message = message_type_payment(type_payment, user.language)


    reply_markup = await edit_type_payment_kb(
        language=user.language,
        type_payment_id=type_payment_id,
        current_index=type_payment.index,
        current_show=type_payment.is_active,
    )

    if send_new_message:
        await send_message(
            chat_id=user.user_id,
            message=message,
            reply_markup=reply_markup,
            image_key='admin_panel',
        )
        return
    await edit_message(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        reply_markup=reply_markup,
        image_key='admin_panel',
    )


@router.callback_query(F.data == "replenishment_editor")
async def replenishment_editor(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=await edit_type_payments_list_kb(user.language)
    )


@router.callback_query(F.data.startswith("edit_type_payment:"))
async def edit_type_payment(callback: CallbackQuery, state: FSMContext, user: Users):
    type_payment_id = int(callback.data.split(':')[1])
    await state.clear()
    await show_type_payment(user, type_payment_id, message_id=callback.message.message_id, callback=callback)


@router.callback_query(F.data.startswith("type_payment_rename:"))
async def type_payment_rename(callback: CallbackQuery, state: FSMContext, user: Users):
    type_payment_id = int(callback.data.split(':')[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_replenishments",
            "Enter a new name\n\nNote: The name must not exceed 200 characters"
        ),
        reply_markup=back_in_edit_type_payment_kb(user.language, type_payment_id)
    )
    await state.update_data(type_payment_id=type_payment_id)
    await state.set_state(GetTypePaymentName.new_name)


@router.message(GetTypePaymentName.new_name)
async def get_type_service_name(message: Message, state: FSMContext, user: Users):
    data = GetTypePaymentNameData(**await state.get_data())

    if len(message.text) > 200:
        domain = "admins_editor_replenishments"
        message_key = "The new name is too long. Please try again"
    else:
        domain = "miscellaneous"
        message_key = "Successfully updated"
        await update_type_payment(type_payment_id=data.type_payment_id, name_for_user=message.text)
        await state.clear()

    await send_message(
        chat_id=user.user_id,
        message=get_text(user.language, domain,message_key),
        reply_markup=back_in_edit_type_payment_kb(user.language, data.type_payment_id)
    )


@router.callback_query(F.data.startswith("type_payment_update_show:"))
async def type_payment_update_show(callback: CallbackQuery, user: Users):
    type_payment_id = int(callback.data.split(':')[1])
    new_is_active = bool(int(callback.data.split(':')[2]))
    await update_type_payment(type_payment_id=type_payment_id, is_active=new_is_active)
    await callback.answer(get_text(user.language,"miscellaneous","Successfully updated"),show_alert=True)
    await show_type_payment(user, type_payment_id, message_id=callback.message.message_id, callback=callback)


@router.callback_query(F.data.startswith("type_payment_update_index:"))
async def type_payment_update_index(callback: CallbackQuery, user: Users):
    type_payment_id = int(callback.data.split(':')[1])
    new_index = int(callback.data.split(':')[2])

    if new_index >= 0:
        await update_type_payment(type_payment_id=type_payment_id, index=new_index)
    await callback.answer(get_text(user.language,"miscellaneous","Successfully updated"),show_alert=True)
    await show_type_payment(user, type_payment_id, message_id=callback.message.message_id, callback=callback)


@router.callback_query(F.data.startswith("type_payment_update_commission:"))
async def type_payment_update_commission(callback: CallbackQuery, state: FSMContext, user: Users):
    type_payment_id = int(callback.data.split(':')[1])
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language,"admins_editor_replenishments","Enter a new commission"),
        reply_markup=back_in_edit_type_payment_kb(user.language, type_payment_id)
    )
    await state.update_data(type_payment_id=type_payment_id)
    await state.set_state(GetTypePaymentCommission.new_commission)


@router.message(GetTypePaymentCommission.new_commission)
async def get_type_service_commission(message: Message, state: FSMContext, user: Users):
    data = GetTypePaymentCommissionData(**await state.get_data())
    new_commission = safe_float_conversion(message.text, positive=True)

    if not new_commission or new_commission > 100:
        message_key = "Incorrect value entered. Please try again"
    else:
        message_key = "Data updated successfully"
        await update_type_payment(type_payment_id=data.type_payment_id, commission=new_commission)
        await state.clear()

    await send_message(
        chat_id=user.user_id,
        message=get_text(user.language,"miscellaneous",message_key),
        reply_markup=back_in_edit_type_payment_kb(user.language, data.type_payment_id)
    )