from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.exceptions.business import ForbiddenError
from src.modules.profile.keyboards import wallet_transactions_kb
from src.modules.profile.services.profile_message import message_show_transaction
from src.services.database.admins.actions import check_admin
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "history_transaction_none")
async def list_is_over(callback: CallbackQuery):
    await callback.answer("Список закончился")


@router.callback_query(F.data.startswith("transaction_list:"))
async def cb_transaction_list(callback: CallbackQuery, user: Users):
    """Данный хендлер используется для админ панели и для пользователя"""
    _, target_user_id, page = callback.data.split(":")
    target_user_id = int(target_user_id)
    page = int(page)

    if target_user_id != user.user_id and not await check_admin(user.user_id):
        raise ForbiddenError()

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, 'profile_messages',"All fund movements. To view a specific transaction, click on it"),
        image_key='history_transections',
        reply_markup=await wallet_transactions_kb(user.language, page, target_user_id, user.user_id),
    )


@router.callback_query(F.data.startswith("transaction_show:"))
async def cb_transaction_show(callback: CallbackQuery, user: Users):
    """Данный хендлер используется для админ панели и для пользователя"""
    _, target_user_id, transaction_id, current_page = callback.data.split(":")
    target_user_id = int(target_user_id)
    transaction_id = int(transaction_id)

    if target_user_id != user.user_id and not await check_admin(user.user_id):
        raise ForbiddenError()

    await message_show_transaction(
        transaction_id,
        user.language,
        callback,
        int(current_page),
        target_user_id,
    )
