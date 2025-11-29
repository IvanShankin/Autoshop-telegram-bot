from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.admin_actions.keyboards import choice_editor_kb
from src.services.database.users.models import Users

router = Router()


@router.callback_query(F.data == "editors")
async def editors(callback: CallbackQuery, user: Users):
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='admin_panel',
        reply_markup=choice_editor_kb(user.language)
    )