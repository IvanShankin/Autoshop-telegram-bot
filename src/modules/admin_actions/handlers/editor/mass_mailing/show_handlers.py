from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards import admin_mailing_kb
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion, safe_parse_datetime
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "admin_mailing")
async def admin_promo(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        image_key="admin_panel",
        reply_markup=admin_mailing_kb(user.language)
    )

# тут продолжить написав handler для списка
# тут продолжить написав handler для списка
# тут продолжить написав handler для списка

