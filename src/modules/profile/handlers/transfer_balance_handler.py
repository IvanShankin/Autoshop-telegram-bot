from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.models.read_models import UsersDTO
from src.services.models.module import ProfileModule
from src.modules.profile.services.checking_data import checking_availability_money, checking_correctness_number
from src.exceptions import UserNotFound, NotEnoughMoney
from src.modules.profile.keyboards import balance_transfer_kb, \
    back_in_balance_transfer_kb, replenishment_and_back_in_transfer_kb, confirmation_transfer_kb
from src.modules.profile.schemas import TransferData
from src.modules.profile.state import TransferMoney
from src.services.bot import Messages
from src.utils.i18n import get_text

router = Router()

@router.callback_query(F.data == "balance_transfer")
async def balance_transfer(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages):
    await state.clear()

    text = get_text(user.language, "profile_messages", "select_desired_action")

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='balance_transfer',
        reply_markup=balance_transfer_kb(user.language, user.user_id)
    )

@router.callback_query(F.data == "transfer_money")
async def transfer_money_start(callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages):
    text = get_text(user.language, "profile_messages", "enter_amount")

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='enter_amount',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(TransferMoney.amount)


@router.message(TransferMoney.amount)
async def transfer_money_get_amount(message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages):
    if not await checking_correctness_number(
        message=message.text,
        language=user.language,
        user_id=user.user_id,
        positive=True,
        reply_markup=back_in_balance_transfer_kb(user.language),
        messages_service=messages_service,
    ):
        await state.set_state(TransferMoney.amount)
        return

    if not await checking_availability_money(
        user_balance=user.balance,
        need_money=int(message.text),
        language=user.language,
        user_id=user.user_id,
        reply_markup=replenishment_and_back_in_transfer_kb(user.language),
        messages_service=messages_service,
    ):
        await state.set_state(TransferMoney.amount)
        return

    await state.update_data(amount=message.text)

    text = get_text(user.language, "profile_messages", "enter_recipient_id")

    await messages_service.send_msg.send(
        chat_id=message.from_user.id,
        message=text,
        event_message_key='enter_user_id',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )

    await state.set_state(TransferMoney.recipient_id)


@router.message(TransferMoney.recipient_id)
async def transfer_money_get_recipient_id(
    message: Message, state: FSMContext, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    if not await checking_correctness_number(
        message=message.text,
        language=user.language,
        user_id=user.user_id,
        positive=False,
        reply_markup=back_in_balance_transfer_kb(user.language),
        messages_service=messages_service
    ):
        await state.set_state(TransferMoney.recipient_id)
        return

    if not await profile_module.user_service.get_user(int(message.text)):
        text = get_text(user.language, "miscellaneous", "user_not_found")
        await messages_service.send_msg.send(
            chat_id=message.from_user.id,
            message=text,
            event_message_key='user_no_found',
            reply_markup=back_in_balance_transfer_kb(user.language)
        )
        await state.set_state(TransferMoney.recipient_id)
        return

    await state.update_data(recipient_id=message.text)
    data = TransferData(**(await state.get_data()))

    text = get_text(
        user.language,
        "profile_messages",
        "check_data_for_accuracy"
    ).format(amount=data.amount, recipient=data.recipient_id)

    await messages_service.send_msg.send(
        chat_id=message.from_user.id,
        message=text,
        event_message_key='confirm_the_data',
        reply_markup=confirmation_transfer_kb(user.language)
    )

@router.callback_query(F.data == "confirm_transfer_money")
async def confirm_transfer_money(
    callback: CallbackQuery,
    state: FSMContext,
    user: UsersDTO,
    profile_module: ProfileModule,
    messages_service: Messages
):
    try:
        data = TransferData(**(await state.get_data()))
    except Exception:
        return

    await state.clear()

    try:
        await profile_module.money_transfer_service.create_transfer(
            sender_id=user.user_id, recipient_id=data.recipient_id, amount=data.amount
        )
    except UserNotFound:
        text_1 = get_text(user.language, "miscellaneous", 'funds_not_written_off')
        text_2 = get_text(user.language, "miscellaneous", "user_not_found")
        await messages_service.edit_msg.edit(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=f'{text_1}\n\n{text_2}',
            event_message_key='user_no_found',
            reply_markup=back_in_balance_transfer_kb(user.language)
        )
        return
    except NotEnoughMoney as e:
        text_1 = get_text(user.language, "miscellaneous", 'funds_not_written_off')
        text_2 = get_text(user.language, "miscellaneous", 'insufficient_funds').format(amount=e.need_money)
        await messages_service.edit_msg.edit(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=f'{text_1}\n\n{text_2}',
            event_message_key='insufficient_funds',
            reply_markup=replenishment_and_back_in_transfer_kb(user.language)
        )
        return

    text = get_text(user.language, "profile_messages", "funds_successfully_transferred")
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='successful_transfer',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )

    recipient = await profile_module.user_service.get_user(data.recipient_id)
    text = get_text(
        user.language,
        "profile_messages",
        "funds_transferred_to_your_balance"
    ).format(amount=data.amount, balance=recipient.balance)
    await messages_service.send_msg.send(
        chat_id=data.recipient_id,
        message=text,
        event_message_key='receiving_funds_from_transfer',
        reply_markup=confirmation_transfer_kb(user.language)
    )
