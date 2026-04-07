from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.models.read_models import UsersDTO
from src.modules.profile.keyboards import type_product_in_purchases_kb
from src.services.bot import Messages
from src.services.models.modules import ProfileModule

router = Router()


@router.callback_query(F.data == "purchases")
async def purchases(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, profile_module: ProfileModule
):
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        event_message_key='purchases',
        reply_markup=await type_product_in_purchases_kb(user.language, user.user_id, profile_module)
    )
