from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.actions import edit_message, send_message
from src.bot_actions.bot_instance import get_bot
from src.exceptions.service_exceptions import UserNotFound, NotEnoughMoney
from src.modules.profile.keyboard_profile import balance_transfer_kb, \
    back_in_balance_transfer_kb, replenishment_and_back_in_transfer_kb, confirmation_transfer_kb, \
    confirmation_voucher_kb
from src.modules.profile.schemas import TransferData
from src.modules.profile.schemas.transfer_balance import CreateVoucherData
from src.modules.profile.state import TransferMoney
from src.modules.profile.state.transfer_balance import CreateVoucher
from src.services.discounts.actions.actions_vouchers import create_voucher as create_voucher_db
from src.services.users.actions import get_user
from src.services.users.actions.action_other_with_user import money_transfer
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_i18n

router = Router()

async def _checking_correctness_number(message: str, language: str, user_id: int, positive: bool) -> bool:
    """
    Проверяет, что message это число, если это не так, то отошлёт пользователю сообщение об это.
    :return Результат (Корректное число = True)
    """
    if not safe_int_conversion(message, positive=positive):
        i18n = get_i18n(language, 'miscellaneous')
        text = i18n.gettext('Incorrect value entered')
        await send_message(
            chat_id=user_id,
            message=text,
            image_key='incorrect_data_entered',
            reply_markup=back_in_balance_transfer_kb(language)
        )
        return False
    return True

async def _checking_availability_money(user_balance: int, need_money: int, language: str, user_id: int):
    """
    Проверяет, что у пользователя достаточно денег если это нет так, то отошлёт пользователю сообщение об это.
    :return Результат (Достаточно = True)
    """
    if user_balance < need_money:
        i18n = get_i18n(language, 'miscellaneous')
        text = i18n.gettext('Insufficient funds: {amount}').format(amount=need_money - user_balance)
        await send_message(
            chat_id=user_id,
            message=text,
            image_key='insufficient_funds',
            reply_markup=replenishment_and_back_in_transfer_kb(language)
        )
        return False
    return True


@router.callback_query(F.data == "balance_transfer")
async def balance_transfer(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    user = await get_user(callback.from_user.id, callback.from_user.username)

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('Select the desired action')

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='balance_transfer',
        reply_markup=balance_transfer_kb(user.language)
    )

@router.callback_query(F.data == "transfer_money")
async def transfer_money_start(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id, callback.from_user.username)

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('Enter the amount')

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='enter_amount',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(TransferMoney.amount)


@router.message(TransferMoney.amount)
async def transfer_money_get_amount(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id, message.from_user.username)

    if not await _checking_correctness_number(
            message=message.text, language=user.language, user_id=user.user_id, positive=True
    ):
        await state.set_state(TransferMoney.amount)
        return

    if not await _checking_availability_money(
            user_balance=user.balance, need_money=int(message.text), language=user.language, user_id=user.user_id
    ):
        await state.set_state(TransferMoney.amount)
        return

    await state.update_data(amount=message.text)

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('Enter the recipients ID')

    await send_message(
        chat_id=message.from_user.id,
        message=text,
        image_key='enter_user_id',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )

    await state.set_state(TransferMoney.recipient_id)


@router.message(TransferMoney.recipient_id)
async def transfer_money_get_recipient_id(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id, message.from_user.username)

    if not await _checking_correctness_number(
            message=message.text, language=user.language, user_id=user.user_id, positive=False
    ):
        await state.set_state(TransferMoney.recipient_id)
        return

    if not await get_user(int(message.text)):
        i18n = get_i18n(user.language, 'miscellaneous')
        text = i18n.gettext('User not found')
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

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext(
        "Check the data for accuracy \n\nAmount: {amount} \nID Recipient: {recipient}"
    ).format(amount=data.amount, recipient=data.recipient_id)

    await send_message(
        chat_id=message.from_user.id,
        message=text,
        image_key='confirm_the_data',
        reply_markup=confirmation_transfer_kb(user.language)
    )

@router.callback_query(F.data == "confirm_transfer_money")
async def confirm_transfer_money(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id, callback.from_user.username)
    data = TransferData(**(await state.get_data()))
    await state.clear()

    try:
        await money_transfer(sender_id=user.user_id, recipient_id=data.recipient_id, amount=data.amount)
    except UserNotFound:
        i18n = get_i18n(user.language, 'miscellaneous')
        text_1 = i18n.gettext('The funds have not been written off')
        text_2 = i18n.gettext('User not found')
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=f'{text_1}\n\n{text_2}',
            image_key='user_no_found',
            reply_markup=back_in_balance_transfer_kb(user.language)
        )
        return
    except NotEnoughMoney as e:
        i18n = get_i18n(user.language, 'miscellaneous')
        text_1 = i18n.gettext('The funds have not been written off')
        text_2 = i18n.gettext('Insufficient funds: {amount}').format(amount=e.need_money)
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=f'{text_1}\n\n{text_2}',
            image_key='insufficient_funds',
            reply_markup=replenishment_and_back_in_transfer_kb(user.language)
        )
        return

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('Funds have been successfully transferred')
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='successful_transfer',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )

    recipient = await get_user(data.recipient_id)
    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext(
        'Funds transferred to your balance: {amount} ₽ \n\nCurrent balance: {balance}'
    ).format(amount=data.amount, balance=recipient.balance)
    await send_message(
        chat_id=data.recipient_id,
        message=text,
        image_key='receiving_funds_from_transfer',
        reply_markup=confirmation_transfer_kb(user.language)
    )


@router.callback_query(F.data == "create_voucher")
async def create_voucher(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id, callback.from_user.username)
    await state.clear()

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('Enter the amount')
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='enter_amount',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(CreateVoucher.amount)

@router.message(CreateVoucher.amount)
async def create_voucher_get_amount(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id, message.from_user.username)

    if not await _checking_correctness_number(
            message=message.text, language=user.language, user_id=user.user_id, positive=True
    ):
        await state.set_state(CreateVoucher.amount)
        return

    await state.update_data(amount=message.text)

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('Enter the number of activations for the voucher')
    await send_message(
        chat_id=message.from_user.id,
        message=text,
        image_key='enter_number_activations_for_voucher',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(CreateVoucher.number_of_activations)

@router.message(CreateVoucher.number_of_activations)
async def create_voucher_get_number_of_activations(message: Message, state: FSMContext):
    user = await get_user(message.from_user.id, message.from_user.username)

    if not await _checking_correctness_number(
            message=message.text, language=user.language, user_id=user.user_id, positive=True
    ):
        await state.set_state(CreateVoucher.number_of_activations)
        return

    await state.update_data(number_of_activations=message.text)
    data = CreateVoucherData(**(await state.get_data()))

    if not await _checking_availability_money(
            user_balance=user.balance, need_money=data.amount * data.number_of_activations, language=user.language, user_id=user.user_id
    ):
        await state.set_state(CreateVoucher.number_of_activations)
        return


    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext(
        "Check the data for accuracy \n\nTotal amount of funds required for activation: {total_sum}\n"
        "Amount of one voucher: {amount} \nNumber of activations: {number_activations}"
    ).format(total_sum=data.amount * data.number_of_activations, amount=data.amount, number_activations=data.number_of_activations)
    await send_message(
        chat_id=message.from_user.id,
        message=text,
        image_key='confirm_the_data',
        reply_markup=confirmation_voucher_kb(user.language)
    )
    await state.set_state(CreateVoucher.amount)

@router.callback_query(F.data == "confirm_create_voucher")
async def confirm_create_voucher(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id, callback.from_user.username)
    data = CreateVoucherData(**(await state.get_data()))
    await state.clear()

    try:
        voucher = await create_voucher_db(
            user_id=user.user_id,
            is_created_admin=False,
            amount=data.amount,
            number_of_activations=data.number_of_activations
        )
    except NotEnoughMoney as e:
        i18n = get_i18n(user.language, 'miscellaneous')
        text_1 = i18n.gettext('The funds have not been written off')
        text_2 = i18n.gettext('Insufficient funds: {amount}').format(amount=e.need_money)
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=f'{text_1}\n\n{text_2}',
            image_key='insufficient_funds',
            reply_markup=replenishment_and_back_in_transfer_kb(user.language)
        )
        return

    bot = await get_bot()
    bot_me = await bot.me()

    i18n = get_i18n(user.language, 'profile_messages')
    text = i18n.gettext(
        "Voucher successfully created. \n\nActivation link: <a href='{link}'>Ссылка</a> \nAmount: {amount} \n"
        "Number of activations: {number_activations} \nTotal amount spent on activation: {total_sum} \n"
        "Current balance: {balance} \n\nNote: One user can only activate one voucher"
    ).format(
        link=f'https://t.me/{bot_me.username}?start=voucher_{voucher.activation_code}',
        amount=data.amount,
        number_activations=data.number_of_activations,
        total_sum=voucher.amount * voucher.number_of_activations,
        balance=user.balance - voucher.amount * voucher.number_of_activations
    )
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='successful_create_voucher',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )



@router.callback_query(F.data == "my_voucher")
async def my_voucher(callback: CallbackQuery):
    pass