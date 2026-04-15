from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import choice_editor_kb


router = Router()


@router.callback_query(F.data == "editors")
async def editors(callback: CallbackQuery, user: UsersDTO, messages_service: Messages):
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        event_message_key='admin_panel',
        reply_markup=choice_editor_kb(user.language)
    )