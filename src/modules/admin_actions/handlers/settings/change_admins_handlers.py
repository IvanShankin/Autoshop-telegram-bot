from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.exceptions import UserNotFound, UnableRemoveMainAdmin, AdminNotFound
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import back_in_admin_settings_kb
from src.modules.admin_actions.state.settings import AddAdmin, DeleteAdmin
from src.utils.converter import safe_int_conversion
from src.infrastructure.translations import get_text

router = Router()

@router.callback_query(F.data == "add_admin")
async def add_admin_handler(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language,"admins_settings", "enter_user_id"),
        reply_markup=back_in_admin_settings_kb(user.language)
    )

    await state.set_state(AddAdmin.user_id)


@router.message(AddAdmin.user_id)
async def add_admin(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    new_user_id = safe_int_conversion(message.text)

    if not new_user_id:
        message = get_text(user.language, "miscellaneous", "incorrect_value_entered")
    else:
        try:
            await admin_module.admin_service.create_admin(new_user_id)
            message = get_text(user.language,"admins_settings", "admin_created_successfully")
            await state.clear()
        except UserNotFound:
            message = get_text(user.language,"admins_settings", "user_not_found")

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=message,
        reply_markup=back_in_admin_settings_kb(user.language)
    )


@router.callback_query(F.data == "delete_admin")
async def delete_admin_handler(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language,"admins_settings", "enter_admin_id"),
        reply_markup=back_in_admin_settings_kb(user.language)
    )

    await state.set_state(DeleteAdmin.user_id)


@router.message(DeleteAdmin.user_id)
async def delete_admin_get_user_id(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages, admin_module: AdminModule
):
    user_id = safe_int_conversion(message.text)

    if not user_id:
        message = get_text(user.language, "miscellaneous", "incorrect_value_entered")
    else:
        try:
            await admin_module.admin_service.delete_admin(user_id)
            message = get_text(user.language,"admins_settings", "admin_successfully_deleted")
            await state.clear()
        except AdminNotFound:
            message = get_text(user.language,"admins_settings", "admin_not_found")
        except UnableRemoveMainAdmin:
            message = get_text(user.language, "admins_settings", "unable_to_remove_main_admin")

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=message,
        reply_markup=back_in_admin_settings_kb(user.language)
    )

