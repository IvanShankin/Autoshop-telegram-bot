from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.bot_actions.checking_data import checking_availability_money, checking_correctness_number
from src.exceptions import UserNotFound, NotEnoughMoney
from src.modules.profile.keyboards import balance_transfer_kb, \
    back_in_balance_transfer_kb, replenishment_and_back_in_transfer_kb, confirmation_transfer_kb
from src.modules.profile.schemas import TransferData
from src.modules.profile.state import TransferMoney
from src.services.database.users.actions import get_user
from src.services.database.users.actions.action_other_with_user import money_transfer
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "balance_transfer")
async def balance_transfer(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()

    text = get_text(user.language, 'profile_messages', 'Select the desired action')

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='balance_transfer',
        reply_markup=balance_transfer_kb(user.language, user.user_id)
    )

@router.callback_query(F.data == "transfer_money")
async def transfer_money_start(callback: CallbackQuery, state: FSMContext, user: Users):
    text = get_text(user.language, 'profile_messages', 'Enter the amount')

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='enter_amount',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(TransferMoney.amount)


@router.message(TransferMoney.amount)
async def transfer_money_get_amount(message: Message, state: FSMContext, user: Users):
    if not await checking_correctness_number(
            message=message.text,
            language=user.language,
            user_id=user.user_id,
            positive=True,
            reply_markup=back_in_balance_transfer_kb(user.language)
    ):
        await state.set_state(TransferMoney.amount)
        return

    if not await checking_availability_money(
            user_balance=user.balance,
            need_money=int(message.text),
            language=user.language,
            user_id=user.user_id,
            reply_markup=replenishment_and_back_in_transfer_kb(user.language)
    ):
        await state.set_state(TransferMoney.amount)
        return

    await state.update_data(amount=message.text)

    text = get_text(user.language, 'profile_messages', 'Enter the recipients ID')

    await send_message(
        chat_id=message.from_user.id,
        message=text,
        image_key='enter_user_id',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )

    await state.set_state(TransferMoney.recipient_id)


@router.message(TransferMoney.recipient_id)
async def transfer_money_get_recipient_id(message: Message, state: FSMContext, user: Users):
    if not await checking_correctness_number(
            message=message.text,
            language=user.language,
            user_id=user.user_id,
            positive=False,
            reply_markup=back_in_balance_transfer_kb(user.language)
    ):
        await state.set_state(TransferMoney.recipient_id)
        return

    if not await get_user(int(message.text)):
        text = get_text(user.language, 'miscellaneous', 'User not found')
        await send_message(
            chat_id=message.from_user.id,
            message=text,
            image_key='user_no_found',
            reply_markup=back_in_balance_transfer_kb(user.language)
        )
        await state.set_state(TransferMoney.recipient_id)
        return

    await state.update_data(recipient_id=message.text)
    data = TransferData(**(await state.get_data()))

    text = get_text(
        user.language,
        'profile_messages',
        "Check the data for accuracy \n\nAmount: {amount} \nID Recipient: {recipient}"
    ).format(amount=data.amount, recipient=data.recipient_id)

    await send_message(
        chat_id=message.from_user.id,
        message=text,
        image_key='confirm_the_data',
        reply_markup=confirmation_transfer_kb(user.language)
    )

@router.callback_query(F.data == "confirm_transfer_money")
async def confirm_transfer_money(callback: CallbackQuery, state: FSMContext, user: Users):
    data = TransferData(**(await state.get_data()))
    await state.clear()

    try:
        await money_transfer(sender_id=user.user_id, recipient_id=data.recipient_id, amount=data.amount)
    except UserNotFound:
        text_1 = get_text(user.language, 'miscellaneous', 'The funds have not been written off')
        text_2 = get_text(user.language, 'miscellaneous', 'User not found')
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=f'{text_1}\n\n{text_2}',
            image_key='user_no_found',
            reply_markup=back_in_balance_transfer_kb(user.language)
        )
        return
    except NotEnoughMoney as e:
        text_1 = get_text(user.language, 'miscellaneous', 'The funds have not been written off')
        text_2 = get_text(user.language, 'miscellaneous', 'Insufficient funds: {amount}').format(amount=e.need_money)
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=f'{text_1}\n\n{text_2}',
            image_key='insufficient_funds',
            reply_markup=replenishment_and_back_in_transfer_kb(user.language)
        )
        return

    text = get_text(user.language, 'profile_messages', 'Funds have been successfully transferred')
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='successful_transfer',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )

    recipient = await get_user(data.recipient_id)
    text = get_text(
        user.language,
        'profile_messages',
        'Funds transferred to your balance: {amount} ₽ \n\nCurrent balance: {balance}'
    ).format(amount=data.amount, balance=recipient.balance)
    await send_message(
        chat_id=data.recipient_id,
        message=text,
        image_key='receiving_funds_from_transfer',
        reply_markup=confirmation_transfer_kb(user.language)
    )
