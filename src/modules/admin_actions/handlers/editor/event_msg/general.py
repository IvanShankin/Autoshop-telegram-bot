from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import event_list_kb
from src.modules.admin_actions.keyboards.editors.event_message_kb import choice_edit_event_msg_kb


router = Router()


@router.callback_query(F.data.startswith("event_msg_editor_list:"))
async def event_msg_editor_list(
    callback: CallbackQuery, user: UsersDTO, admin_module: AdminModule, messages_service: Messages,
):
    current_page = int(callback.data.split(':')[1])

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=await event_list_kb(user.language, current_page, admin_module=admin_module)
    )


@router.callback_query(F.data.startswith("choice_edit_event_msg:"))
async def choice_edit_event_msg(callback: CallbackQuery, user: UsersDTO, messages_service: Messages,):
    event_msg_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=await choice_edit_event_msg_kb(user.language, event_msg_key, current_page)
    )