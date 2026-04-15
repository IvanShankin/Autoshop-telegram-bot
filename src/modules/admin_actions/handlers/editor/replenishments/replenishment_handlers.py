from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.models.update_models import UpdateTypePaymentDTO
from src.modules.admin_actions.keyboards.editors.replenishment_kb import edit_type_payments_list_kb, edit_type_payment_kb, \
    back_in_edit_type_payment_kb
from src.modules.admin_actions.schemas import GetTypePaymentNameData, GetTypePaymentCommissionData
from src.modules.admin_actions.services import safe_get_type_payment
from src.modules.admin_actions.services import message_type_payment
from src.modules.admin_actions.state import GetTypePaymentName, GetTypePaymentCommission

from src.utils.converter import safe_float_conversion
from src.utils.i18n import get_text


router = Router()


async def show_type_payment(
    user: UsersDTO,
    type_payment_id: int,
    messages_service: Messages,
    admin_module: AdminModule,
    send_new_message: bool = False,
    message_id: int = None,
    callback: CallbackQuery = None
):
    type_payment = await safe_get_type_payment(
        type_payment_id=type_payment_id,
        user=user,
        callback=callback,
        messages_service=messages_service,
        admin_module=admin_module,
    )
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
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=message,
            reply_markup=reply_markup,
            event_message_key='admin_panel',
        )
        return
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        reply_markup=reply_markup,
        event_message_key='admin_panel',
    )


@router.callback_query(F.data == "replenishment_editor")
async def replenishment_editor(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    await state.clear()
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=await edit_type_payments_list_kb(user.language, admin_module)
    )


@router.callback_query(F.data.startswith("edit_type_payment:"))
async def edit_type_payment(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    type_payment_id = int(callback.data.split(':')[1])
    await state.clear()
    await show_type_payment(
        user,
        type_payment_id,
        message_id=callback.message.message_id,
        callback=callback,
        messages_service=messages_service,
        admin_module=admin_module,
    )


@router.callback_query(F.data.startswith("type_payment_rename:"))
async def type_payment_rename(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    type_payment_id = int(callback.data.split(':')[1])
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_replenishments",
            "enter_new_name_for_service"
        ),
        reply_markup=back_in_edit_type_payment_kb(user.language, type_payment_id)
    )
    await state.update_data(type_payment_id=type_payment_id)
    await state.set_state(GetTypePaymentName.new_name)


@router.message(GetTypePaymentName.new_name)
async def get_type_service_name(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    data = GetTypePaymentNameData(**await state.get_data())

    if len(message.text) > 200:
        domain = "admins_editor_replenishments"
        message_key = "new_name_too_long"
    else:
        domain = "miscellaneous"
        message_key = "successfully_updated"
        await admin_module.type_payments_service.update_type_payment(
            type_payment_id=data.type_payment_id,
            data=UpdateTypePaymentDTO(name_for_user=message.text),
            make_commit=True,
            filling_redis=True,
        )
        await state.clear()

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(user.language, domain,message_key),
        reply_markup=back_in_edit_type_payment_kb(user.language, data.type_payment_id)
    )


@router.callback_query(F.data.startswith("type_payment_update_show:"))
async def type_payment_update_show(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    type_payment_id = int(callback.data.split(':')[1])
    new_is_active = bool(int(callback.data.split(':')[2]))

    await admin_module.type_payments_service.update_type_payment(
        type_payment_id=type_payment_id,
        data=UpdateTypePaymentDTO(is_active=new_is_active),
        make_commit=True,
        filling_redis=True,
    )
    await callback.answer(get_text(user.language,"miscellaneous","successfully_updated"),show_alert=True)

    await show_type_payment(
        user,
        type_payment_id,
        message_id=callback.message.message_id,
        callback=callback,
        messages_service=messages_service,
        admin_module=admin_module,
    )


@router.callback_query(F.data.startswith("type_payment_update_index:"))
async def type_payment_update_index(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    type_payment_id = int(callback.data.split(':')[1])
    new_index = int(callback.data.split(':')[2])

    if new_index >= 0:
        await admin_module.type_payments_service.update_type_payment(
            type_payment_id=type_payment_id,
            data=UpdateTypePaymentDTO(index=new_index),
            make_commit=True,
            filling_redis=True,
        )

    await callback.answer(get_text(user.language,"miscellaneous","successfully_updated"),show_alert=True)
    await show_type_payment(
        user,
        type_payment_id,
        message_id=callback.message.message_id,
        callback=callback,
        messages_service=messages_service,
        admin_module=admin_module,
    )


@router.callback_query(F.data.startswith("type_payment_update_commission:"))
async def type_payment_update_commission(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    type_payment_id = int(callback.data.split(':')[1])

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language,"admins_editor_replenishments","enter_new_commission"),
        reply_markup=back_in_edit_type_payment_kb(user.language, type_payment_id)
    )

    await state.update_data(type_payment_id=type_payment_id)
    await state.set_state(GetTypePaymentCommission.new_commission)


@router.message(GetTypePaymentCommission.new_commission)
async def get_type_service_commission(
    message: Message, state: FSMContext, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    data = GetTypePaymentCommissionData(**await state.get_data())
    new_commission = safe_float_conversion(message.text, positive=True)

    if not new_commission or new_commission > 100:
        message_key = "incorrect_value_entered"
    else:
        message_key = "data_updated_successfully"

        await admin_module.type_payments_service.update_type_payment(
            type_payment_id=data.type_payment_id,
            data=UpdateTypePaymentDTO(commission=new_commission),
            make_commit=True,
            filling_redis=True,
        )
        await state.clear()

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(user.language,"miscellaneous",message_key),
        reply_markup=back_in_edit_type_payment_kb(user.language, data.type_payment_id)
    )