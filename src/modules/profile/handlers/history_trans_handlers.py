from aiogram import Router, F
from aiogram.types import CallbackQuery

from src.models.read_models import UsersDTO
from src.modules.profile.keyboards import wallet_transactions_kb, back_in_wallet_transactions_kb
from src.application.models.modules import ProfileModule
from src.application.bot import Messages
from src.infrastructure.translations import get_text

router = Router()

@router.callback_query(F.data == "history_transaction_none")
async def list_is_over(callback: CallbackQuery, user: UsersDTO,):
    await callback.answer(
        get_text(user.language, "profile_messages", "list_is_over")
    )


@router.callback_query(F.data.startswith("transaction_list:"))
async def cb_transaction_list(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    """Данный хендлер используется для админ панели и для пользователя"""
    _, target_user_id, page = callback.data.split(":")
    target_user_id = int(target_user_id)
    page = int(page)

    await profile_module.permission_service.check_permission(
        current_user_id=user.user_id, target_user_id=target_user_id
    )

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "profile_messages","all_fund_movements"),
        event_message_key='history_transections',
        reply_markup=await wallet_transactions_kb(user.language, page, target_user_id, user.user_id, profile_module),
    )


@router.callback_query(F.data.startswith("transaction_show:"))
async def cb_transaction_show(
    callback: CallbackQuery, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    """Данный хендлер используется для админ панели и для пользователя"""
    _, target_user_id, transaction_id, current_page = callback.data.split(":")
    target_user_id = int(target_user_id)
    transaction_id = int(transaction_id)

    await profile_module.permission_service.check_permission(
        current_user_id=user.user_id, target_user_id=target_user_id
    )

    transaction = await profile_module.wallet_transaction_service.get_wallet_transaction(transaction_id)

    if transaction is None:
        await callback.answer(text=get_text(user.language, "miscellaneous", 'data_not_found'), show_alert=True)
        return

    text = get_text(
        user.language,
        "profile_messages",
        "transaction_details"
    ).format(
        transaction_id=transaction.wallet_transaction_id,
        type=get_text(user.language, "type_wallet_transaction", f'{transaction.type}'),
        amount=transaction.amount,
        balance_before=transaction.balance_before,
        balance_after=transaction.balance_after,
        created_at=profile_module.dt_formatter.format(transaction.created_at),
    )

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='history_transections',
        reply_markup=back_in_wallet_transactions_kb(user.language, target_user_id, current_page=int(current_page))
    )
