from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.modules.profile.keyboards import type_product_in_purchases_kb
from src.services.database.users.models import Users

router = Router()


@router.callback_query(F.data == "purchases")
async def purchases(callback: CallbackQuery, user: Users):
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='purchased_accounts',
        reply_markup=await type_product_in_purchases_kb(user.language, user.user_id)
    )
