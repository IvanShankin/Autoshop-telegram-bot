from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.bot_actions.actions import edit_message
from src.config import DT_FORMAT
from src.modules.profile.keyboard_profile import all_wallet_transactions_kb, back_in_wallet_transactions_kb
from src.services.users.actions import get_user
from src.services.users.actions.action_other_with_user import get_wallet_transactions_by_user, get_wallet_transaction
from src.utils.i18n import get_i18n

router = Router()

@router.callback_query(F.data == "history_transaction")
async def show_all_history_transaction(callback: CallbackQuery):
    user = await get_user(callback.from_user.id, callback.from_user.username)

    transactions = await get_wallet_transactions_by_user(user.user_id)

    i18n = get_i18n(user.language, "profile_messages")
    text = i18n.gettext('All fund movements. To view a specific transaction, click on it')

    await edit_message(
        chat_id = callback.from_user.id,
        message_id = callback.message.message_id,
        message = text,
        image_key = 'history_transections',
        reply_markup = all_wallet_transactions_kb(transactions, user.language)
    )
    
@router.callback_query(F.data.startswith('show_transaction:'))
async def show_transaction(callback: CallbackQuery):
    transaction_id = callback.data.split(':')[1]
    user = await get_user(callback.from_user.id, callback.from_user.username)
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

