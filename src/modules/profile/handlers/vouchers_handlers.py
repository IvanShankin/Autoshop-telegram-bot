from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.bot_instance import get_bot
from src.models.create_models.discounts import CreateVoucherDTO
from src.models.read_models import UsersDTO
from src.modules.profile.services.checking_data import checking_availability_money, checking_correctness_number
from src.exceptions import NotEnoughMoney
from src.modules.profile.keyboards import back_in_balance_transfer_kb, replenishment_and_back_in_transfer_kb, \
    confirmation_voucher_kb, all_vouchers_kb, back_in_all_voucher_kb, show_voucher_kb, confirm_deactivate_voucher_kb
from src.modules.profile.schemas.transfer_balance import CreateVoucherData
from src.modules.profile.state.transfer_balance import CreateVoucher

from src.services.bot import Messages
from src.services.models.module import ProfileModule
from src.utils.i18n import get_text

router = Router()



@router.callback_query(F.data == "create_voucher")
async def create_voucher(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await state.clear()

    text = get_text(user.language, "profile_messages", "enter_amount")
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='enter_amount',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(CreateVoucher.amount)


@router.message(CreateVoucher.amount)
async def create_voucher_get_amount(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    if not await checking_correctness_number(
        message=message.text,
        language=user.language,
        user_id=user.user_id,
        positive=True,
        reply_markup=back_in_balance_transfer_kb(user.language),
        messages_service=messages_service
    ):
        await state.set_state(CreateVoucher.amount)
        return

    await state.update_data(amount=message.text)

    text = get_text(user.language, "profile_messages", "enter_number_of_activations_for_voucher")
    await messages_service.send_msg.send(
        chat_id=message.from_user.id,
        message=text,
        event_message_key='enter_number_activations_for_voucher',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )
    await state.set_state(CreateVoucher.number_of_activations)


@router.message(CreateVoucher.number_of_activations)
async def create_voucher_get_number_of_activations(
        message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    if not await checking_correctness_number(
        message=message.text,
        language=user.language,
        user_id=user.user_id,
        positive=True,
        reply_markup=back_in_balance_transfer_kb(user.language),
        messages_service=messages_service
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
        reply_markup=replenishment_and_back_in_transfer_kb(user.language),
        messages_service=messages_service,
    ):
        await state.set_state(CreateVoucher.number_of_activations)
        return

    text = get_text(
        user.language,
        "profile_messages",
        "check_voucher_data_for_accuracy"
    ).format(total_sum=data.amount * data.number_of_activations, amount=data.amount, number_activations=data.number_of_activations)
    await messages_service.send_msg.send(
        chat_id=message.from_user.id,
        message=text,
        event_message_key='confirm_the_data',
        reply_markup=confirmation_voucher_kb(user.language)
    )
    await state.set_state(CreateVoucher.amount)


@router.callback_query(F.data == "confirm_create_voucher")
async def confirm_create_voucher(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages, profile_module: ProfileModule,
):
    data = CreateVoucherData(**(await state.get_data()))
    await state.clear()

    try:
        voucher = await profile_module.voucher_service.create_voucher(
            user_id=user.user_id,
            data=CreateVoucherDTO(
                is_created_admin=False,
                amount=data.amount,
                number_of_activations=data.number_of_activations
            )
        )
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

    bot = get_bot()
    bot_me = await bot.me()

    text = get_text(
        user.language,
        "profile_messages",
        "voucher_successfully_created"
    ).format(
        link=f'https://t.me/{bot_me.username}?start=voucher_{voucher.activation_code}',
        amount=data.amount,
        number_activations=data.number_of_activations,
        total_sum=voucher.amount * voucher.number_of_activations,
        balance=user.balance - voucher.amount * voucher.number_of_activations
    )
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='successful_create_voucher',
        reply_markup=back_in_balance_transfer_kb(user.language)
    )


@router.callback_query(F.data.startswith("voucher_list:"))
async def voucher_list(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages,
):
    target_user_id = callback.data.split(":")[1]
    current_page = callback.data.split(":")[2]

    text = get_text(user.language, "profile_messages", "all_vouchers_list")

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='viewing_vouchers',
        reply_markup=await all_vouchers_kb(
            current_page=int(current_page),
            target_user_id=int(target_user_id),
            user_id=user.user_id,
            language=user.language
        )
    )


@router.callback_query(F.data.startswith("show_voucher:"))
async def show_voucher(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, profile_module: ProfileModule,
):
    target_user_id = int(callback.data.split(':')[1])
    current_page = int(callback.data.split(':')[2])
    voucher_id = int(callback.data.split(":")[3])

    voucher = await profile_module.voucher_service.get_voucher_by_id(voucher_id)

    await profile_module.permission_service.check_permission(
        current_user_id=user.user_id, target_user_id=target_user_id
    )

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
        reply_markup = back_in_all_voucher_kb(user.language, current_page, target_user_id)
    else:
        bot = get_bot()
        bot_me = await bot.me()
        text = get_text(
            user.language,
            "profile_messages",
            "voucher_details"
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

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='viewing_vouchers',
        reply_markup=reply_markup
    )


@router.callback_query(F.data.startswith("confirm_deactivate_voucher:"))
async def confirm_deactivate_voucher(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, profile_module: ProfileModule,
):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await profile_module.voucher_service.get_voucher_by_id(voucher_id)

    await profile_module.permission_service.check_permission(
        current_user_id=user.user_id, target_user_id=voucher.creator_id
    )

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
        reply_markup = back_in_all_voucher_kb(user.language, current_page, user.user_id)
        image_key = 'viewing_vouchers'
    else:
        text = get_text(
            user.language,
            "profile_messages",
            "confirmation_deactivate_voucher"
        ).format(amount=voucher.amount * (voucher.number_of_activations - voucher.activated_counter))
        image_key = 'confirm_deactivate_voucher'
        reply_markup = confirm_deactivate_voucher_kb(user.language, current_page, user.user_id, voucher_id)

    await messages_service.edit_msg.edit(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=text,
            event_message_key=image_key,
            reply_markup=reply_markup
    )

@router.callback_query(F.data.startswith("deactivate_voucher:"))
async def deactivate_voucher(
    callback: CallbackQuery, user: UsersDTO, messages_service: Messages, profile_module: ProfileModule,
):
    voucher_id = int(callback.data.split(":")[1])
    current_page = int(callback.data.split(':')[2])

    voucher = await profile_module.voucher_service.get_voucher_by_id(voucher_id)

    await profile_module.permission_service.check_permission(
        current_user_id=user.user_id, target_user_id=voucher.creator_id
    )

    if not voucher or not voucher.is_valid:
        text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
        image_key = 'voucher_successful_deactivate'
    else:
        try:
            await profile_module.voucher_service.deactivate_voucher(voucher_id)

            user = await profile_module.user_service.get_user(callback.from_user.id, callback.from_user.username)

            text = get_text(user.language, "profile_messages",
                "voucher_successfully_deactivated"
            ).format(amount=voucher.amount * (voucher.number_of_activations - voucher.activated_counter), balance=user.balance)
            image_key = 'voucher_successful_deactivate'
        except Exception as e:
            profile_module.logger.exception("Ошибка при деактивации ваучера")
            settings = await profile_module.settings_service.get_settings()

            text = get_text(user.language, "profile_messages",
                "error_deactivating_voucher"
            ).format(username_support=settings.support_username)
            image_key = 'server_error'

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key=image_key,
        reply_markup=back_in_all_voucher_kb(user.language, current_page, user.user_id)
    )