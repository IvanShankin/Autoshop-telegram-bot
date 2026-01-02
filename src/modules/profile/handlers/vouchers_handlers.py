from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.bot_actions.bot_instance import get_bot
from src.bot_actions.checking_data import checking_availability_money, checking_correctness_number
from src.exceptions import NotEnoughMoney
from src.modules.profile.keyboard_profile import back_in_balance_transfer_kb, replenishment_and_back_in_transfer_kb, \
    confirmation_voucher_kb, all_vouchers_kb, back_in_all_voucher_kb, show_voucher_kb, confirm_deactivate_voucher_kb
from src.modules.profile.schemas.transfer_balance import CreateVoucherData
from src.modules.profile.state.transfer_balance import CreateVoucher
from src.services.database.discounts.actions import (create_voucher as create_voucher_db, get_voucher_by_id,
                                                     deactivate_voucher as deactivate_voucher_server)
from src.services.database.system.actions import get_settings
from src.services.database.users.actions import get_user
from src.services.database.users.models import Users
from src.utils.i18n import get_text

router = Router()



@router.callback_query(F.data == "create_voucher")
async def create_voucher(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()

    text = get_text(user.language, 'profile_messages', 'Enter the amount')
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='enter_amount',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(CreateVoucher.amount)


@router.message(CreateVoucher.amount)
async def create_voucher_get_amount(message: Message, state: FSMContext, user: Users):
    if not await checking_correctness_number(
            message=message.text,
            language=user.language,
            user_id=user.user_id,
            positive=True,
            reply_markup=back_in_balance_transfer_kb(user.language)
    ):
        await state.set_state(CreateVoucher.amount)
        return

    await state.update_data(amount=message.text)

    text = get_text(user.language, 'profile_messages', 'Enter the number of activations for the voucher')
    await send_message(
        chat_id=message.from_user.id,
        message=text,
        image_key='enter_number_activations_for_voucher',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(CreateVoucher.number_of_activations)


@router.message(CreateVoucher.number_of_activations)
async def create_voucher_get_number_of_activations(message: Message, state: FSMContext, user: Users):
    if not await checking_correctness_number(
            message=message.text,
            language=user.language,
            user_id=user.user_id,
            positive=True,
            reply_markup=back_in_balance_transfer_kb(user.language)
    ):
        await state.set_state(CreateVoucher.number_of_activations)
        return

    await state.update_data(number_of_activations=message.text)
    data = CreateVoucherData(**(await state.get_data()))

    if not await checking_availability_money(
            user_balance=user.balance,
            need_money=data.amount * data.number_of_activations,
            language=user.language,
            user_id=user.user_id,
            reply_markup=replenishment_and_back_in_transfer_kb(user.language)
    ):
        await state.set_state(CreateVoucher.number_of_activations)
        return

    text = get_text(
        user.language,
        'profile_messages',
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
async def confirm_create_voucher(callback: CallbackQuery, state: FSMContext, user: Users):
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

    bot = await get_bot()
    bot_me = await bot.me()

    text = get_text(
        user.language,
        'profile_messages',
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


@router.callback_query(F.data.startswith("voucher_list:"))
async def voucher_list(callback: CallbackQuery, user: Users):
    target_user_id = callback.data.split(":")[1]
    current_page = callback.data.split(":")[2]

    text = get_text(user.language, 'profile_messages', "All vouchers. To view a specific voucher, click on it")

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='viewing_vouchers',
        reply_markup=await all_vouchers_kb(
            current_page=int(current_page),
            target_user_id=int(target_user_id),
            user_id=user.user_id,
            language=user.language
        )
    )


@router.callback_query(F.data.startswith("show_voucher:"))
async def show_voucher(callback: CallbackQuery, user: Users):
    target_user_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])
    voucher_id = int(callback.data.split(":")[3])

    voucher = await get_voucher_by_id(voucher_id)

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, 'profile_messages', 'This voucher is currently inactive, please select another one')
        reply_markup=back_in_all_voucher_kb(user.language, current_page, target_user_id)
    else:
        bot = await get_bot()
        bot_me = await bot.me()
        text = get_text(user.language, 'profile_messages',
            "ID: {id} \n\nLink: <a href='{link}'>Copy</a> \nTotal spent: {total_amount} \nAmount: {amount} \n"
            "Allowed number of activations: {number_of_activations} \nNumber of activations: {activated_counter}"
        ).format(
            id=voucher_id,
            link=f'https://t.me/{bot_me.username}?start=voucher_{voucher.activation_code}',
            total_amount=voucher.amount * voucher.number_of_activations,
            amount=voucher.amount,
            number_of_activations=voucher.number_of_activations,
            activated_counter=voucher.activated_counter
        )
        reply_markup = show_voucher_kb(
            language=user.language,
            current_page=current_page,
            target_user_id=target_user_id,
            user_id=user.user_id,
            voucher_id=voucher_id
        )

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='viewing_vouchers',
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("confirm_deactivate_voucher:"))
async def confirm_deactivate_voucher(callback: CallbackQuery, user: Users):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await get_voucher_by_id(voucher_id)

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, 'profile_messages', 'This voucher is currently inactive')
        reply_markup = back_in_all_voucher_kb(user.language, current_page, user.user_id)
        image_key = 'viewing_vouchers'
    else:
        text = get_text(user.language, 'profile_messages',
            "Are you sure you want to deactivate the voucher? \nAmount to be refunded: {amount}"
        ).format(amount=voucher.amount * (voucher.number_of_activations - voucher.activated_counter))
        image_key = 'confirm_deactivate_voucher'
        reply_markup = confirm_deactivate_voucher_kb(user.language, current_page, user.user_id, voucher_id)

    await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=text,
            image_key=image_key,
            reply_markup=reply_markup
    )

@router.callback_query(F.data.startswith("deactivate_voucher:"))
async def deactivate_voucher(callback: CallbackQuery, user: Users):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await get_voucher_by_id(voucher_id)

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, 'profile_messages', 'This voucher is currently inactive')
        image_key = 'voucher_successful_deactivate'
    else:
        try:
            await deactivate_voucher_server(voucher_id)
            user = await get_user(callback.from_user.id, callback.from_user.username)
            text = get_text(user.language, 'profile_messages',
                "The voucher has been successfully deactivated \n\nYour account has been credited with: {amount} \nCurrent balance: {balance}"
            ).format(amount=voucher.amount * (voucher.number_of_activations - voucher.activated_counter), balance=user.balance)
            image_key = 'voucher_successful_deactivate'
        except Exception as e:
            settings = await get_settings()

            text = get_text(user.language, 'profile_messages',
                'There was an error deactivating your voucher \n\nIf your funds have not been returned, please contact support: @{username_support}'
            ).format(username_support=settings.support_username)
            image_key = 'server_error'

    await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=text,
            image_key=image_key,
            reply_markup=back_in_all_voucher_kb(user.language, current_page, user.user_id)
    )