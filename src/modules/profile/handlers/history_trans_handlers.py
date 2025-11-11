from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.actions import edit_message
from src.config import DT_FORMAT
from src.modules.profile.keyboard_profile import back_in_wallet_transactions_kb,  wallet_transactions_kb
from src.services.database.users.actions.action_other_with_user import get_wallet_transaction
from src.services.database.users.models import Users
from src.utils.i18n import get_i18n

router = Router()

@router.callback_query(F.data == "history_transaction_none")
async def list_is_over(callback: CallbackQuery):
    await callback.answer("Список закончился")

@router.callback_query(F.data.startswith("history_transaction:"))
async def show_all_history_transaction(callback: CallbackQuery, user: Users):
    current_page = callback.data.split(':')[1]

    i18n = get_i18n(user.language, "profile_messages")
    text = i18n.gettext('All fund movements. To view a specific transaction, click on it')

    await edit_message(
        chat_id = callback.from_user.id,
        message_id = callback.message.message_id,
        message = text,
        image_key = 'history_transections',
        reply_markup = await wallet_transactions_kb(user.language, int(current_page), user.user_id)
    )

@router.callback_query(F.data.startswith('show_transaction:'))
async def show_transaction(callback: CallbackQuery, user: Users):
    transaction_id = callback.data.split(':')[1]
    transaction = await get_wallet_transaction(int(transaction_id))

    if transaction is None:
        i18n = get_i18n(user.language, 'miscellaneous')
        await callback.answer(text=i18n.gettext('Data not found'), show_alert=True)

    i18n_type = get_i18n(user.language, "type_wallet_transaction")
    i18n_profile = get_i18n(user.language, "profile_messages")
    text = i18n_profile.gettext(
        "ID: {transaction_id}\n\n"
        "Type: {type}\n"
        "Amount: {amount}\n"
        "Balance before: {balance_before}\n"
        "Balance after: {balance_after}\n"
        "Date: {created_at}"
    ).format(
        transaction_id=transaction.wallet_transaction_id,
        type=i18n_type.gettext(f'{transaction.type}'),
        amount=transaction.amount,
        balance_before=transaction.balance_before,
        balance_after=transaction.balance_after,
        created_at=transaction.created_at.strftime(DT_FORMAT),
    )

    await edit_message(
        chat_id = callback.from_user.id,
        message_id = callback.message.message_id,
        message = text,
        image_key = 'history_transections',
        reply_markup = back_in_wallet_transactions_kb(user.language)
    )

