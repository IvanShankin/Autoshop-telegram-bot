from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.admin_actions.keyboards.statistics_kb import admin_statistics_kb
from src.modules.admin_actions.services.statistics_msg import get_statistics_message
from src.services.database.users.models import Users

router = Router()

@router.callback_query(F.data.startswith("admin_statistics:"))
async def admin_statistics(callback: CallbackQuery, user: Users):
    interval_days = int(callback.data.split(":")[1])
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=await get_statistics_message(interval_days, user.language),
        image_key='admin_panel',
        reply_markup=admin_statistics_kb(language=user.language, current_days=interval_days)
    )