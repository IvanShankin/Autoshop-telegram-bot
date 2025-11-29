from aiogram.types import CallbackQuery

from src.bot_actions.messages import edit_message
from src.bot_actions.bot_instance import get_bot
from src.config import DT_FORMAT
from src.modules.profile.keyboard_profile import back_in_wallet_transactions_kb, back_in_accrual_ref_list_kb
from src.services.database.discounts.actions import get_valid_voucher_by_user_page
from src.services.database.referrals.models import IncomeFromReferrals
from src.services.database.users.actions import get_wallet_transaction, get_user
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def get_main_message_profile(user: Users, language: str) -> str:
    """
    Вернёт сообщение с данными о пользователе
    :param user: пользователя о котором будут выведены данные
    :param language: На каком языке вернуть сообщение. Для него отдельный параметр т.к. данная функция ещё используется для админа
    """
    username = get_text(language, 'profile_messages', 'No') if user.username is None else f'@{user.username}'

    bot = await get_bot()
    bot_me = await bot.me()
    vouchers = await get_valid_voucher_by_user_page(user.user_id)

    money_in_vouchers = 0
    for voucher in vouchers:
        money_in_vouchers += voucher.amount * (voucher.number_of_activations - voucher.activated_counter)

    return get_text(
        language,
        'profile_messages',
        "Username: {username} \nID: {id} \nRef_link: {ref_link} \nTotal sum replenishment: {total_sum_replenishment}"
        "\nBalance: {balance}, \nMoney in vouchers {money_in_vouchers}"
    ).format(
        username=username,
        id=user.user_id,
        ref_link=f'https://t.me/{bot_me.username}?start=ref_{user.unique_referral_code}',
        total_sum_replenishment=user.total_sum_replenishment,
        balance=user.balance,
        money_in_vouchers=money_in_vouchers,
    )


async def message_show_transaction(
    transaction_id: int,
    language: str,
    callback: CallbackQuery,
    currant_page: int,
    target_user_id: int = None,
):
    transaction = await get_wallet_transaction(transaction_id)

    if transaction is None:
        await callback.answer(text=get_text(language, 'miscellaneous', 'Data not found'), show_alert=True)

    text = get_text(
        language,
        "profile_messages",
        "ID: {transaction_id}\n\n"
        "Type: {type}\n"
        "Amount: {amount}\n"
        "Balance before: {balance_before}\n"
        "Balance after: {balance_after}\n"
        "Date: {created_at}"
    ).format(
        transaction_id=transaction.wallet_transaction_id,
        type=get_text(language, "type_wallet_transaction", f'{transaction.type}'),
        amount=transaction.amount,
        balance_before=transaction.balance_before,
        balance_after=transaction.balance_after,
        created_at=transaction.created_at.strftime(DT_FORMAT),
    )

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='history_transections',
        reply_markup=back_in_wallet_transactions_kb(language, target_user_id, currant_page=currant_page)
    )

async def message_income_ref(
    income: IncomeFromReferrals,
    callback, language: str,
    current_page: int,
):
    referral_user = await get_user(income.referral_id)
    username = f"@{referral_user.username}" if referral_user.username else 'None'

    text = get_text(
        language,
        'profile_messages',
        "ID: {id}\n\n"
        "Referral Username: {username}\n"
        "Amount: {amount}\n"
        "Percentage of Replenishment: {percentage_of_replenishment}\n"
        "Date: {date}\n"
    ).format(
        id=income.income_from_referral_id,
        username=username,
        amount=income.amount,
        percentage_of_replenishment=income.percentage_of_replenishment,
        date=income.created_at.strftime(DT_FORMAT),
    )

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='history_income_from_referrals',
        reply_markup= await back_in_accrual_ref_list_kb(language, current_page, income.owner_user_id)
    )