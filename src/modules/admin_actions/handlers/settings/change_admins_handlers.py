from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.exceptions import UserNotFound, UnableRemoveMainAdmin, AdminNotFound
from src.modules.admin_actions.keyboards import back_in_admin_settings_kb
from src.modules.admin_actions.state.settings import AddAdmin, DeleteAdmin
from src.services.database.admins.actions import create_admin
from src.services.database.admins.actions.actions_admin import delete_admin
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "add_admin")
async def add_admin_handler(callback: CallbackQuery, state: FSMContext, user: Users):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language,"admins_settings", "enter_user_id"),
        reply_markup=back_in_admin_settings_kb(user.language)
    )

    await state.set_state(AddAdmin.user_id)


@router.message(AddAdmin.user_id)
async def add_admin(message: Message, state: FSMContext, user: Users):
    new_user_id = safe_int_conversion(message.text)

    if not new_user_id:
        message = get_text(user.language, "miscellaneous", "incorrect_value_entered")
    else:
        try:
            await create_admin(new_user_id)
            message = get_text(user.language,"admins_settings", "admin_created_successfully")
            await state.clear()
        except UserNotFound:
            message = get_text(user.language,"admins_settings", "user_not_found")

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=back_in_admin_settings_kb(user.language)
    )


@router.callback_query(F.data == "delete_admin")
async def delete_admin_handler(callback: CallbackQuery, state: FSMContext, user: Users):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(user.language,"admins_settings", "enter_admin_id"),
        reply_markup=back_in_admin_settings_kb(user.language)
    )

    await state.set_state(DeleteAdmin.user_id)


@router.message(DeleteAdmin.user_id)
async def delete_admin_get_user_id(message: Message, state: FSMContext, user: Users):
    user_id = safe_int_conversion(message.text)

    if not user_id:
        message = get_text(user.language, "miscellaneous", "incorrect_value_entered")
    else:
        try:
            await delete_admin(user_id)
            message = get_text(user.language,"admins_settings", "admin_successfully_deleted")
            await state.clear()
        except AdminNotFound:
            message = get_text(user.language,"admins_settings", "admin_not_found")
        except UnableRemoveMainAdmin:
            message = get_text(user.language, "admins_settings", "unable_to_remove_main_admin")

    await send_message(
        chat_id=user.user_id,
        message=message,
        reply_markup=back_in_admin_settings_kb(user.language)
    )

