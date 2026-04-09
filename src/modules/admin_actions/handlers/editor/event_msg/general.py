from aiogram import Router, F
from aiogram.types import CallbackQuery

from src._bot_actions.messages import edit_message
from src.modules.admin_actions.keyboards import images_list_kb
from src.modules.admin_actions.keyboards.editors.event_message_kb import choice_edit_event_msg_kb
from src.database.models.users import Users


router = Router()


@router.callback_query(F.data.startswith("event_msg_editor_list:"))
async def event_msg_editor_list(callback: CallbackQuery, user: Users):
    current_page = int(callback.data.split(':')[1])

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=await images_list_kb(user.language, current_page)
    )


@router.callback_query(F.data.startswith("choice_edit_event_msg:"))
async def choice_edit_event_msg(callback: CallbackQuery, user: Users):
    event_msg_key = str(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])

    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        event_message_key="admin_panel",
        reply_markup=await choice_edit_event_msg_kb(user.language, event_msg_key, current_page)
    )