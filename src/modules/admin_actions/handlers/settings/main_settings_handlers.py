from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.admin_actions.keyboards import admin_settings_kb
from src.services.database.users.models import Users

router = Router()


@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=admin_settings_kb(user.language)
    )