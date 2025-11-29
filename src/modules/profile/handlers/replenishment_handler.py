from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.bot_actions.checking_data import checking_correctness_number
from src.config import PAYMENT_LIFETIME_SECONDS, MIN_MAX_REPLENISHMENT
from src.modules.profile.keyboard_profile import type_replenishment_kb, back_in_type_replenishment_kb, payment_invoice
from src.modules.profile.schemas.replenishment import GetAmountData
from src.modules.profile.state.replenishment import GetAmount
from src.services.database.system.actions.actions import get_type_payment
from src.services.database.users.models import Users
from src.services.payments.crypto_bot.client import crypto_bot
from src.utils.i18n import get_text, n_get_text

router_with_repl_kb = Router()
router = Router()


@router.callback_query(F.data == "show_type_replenishment")
async def show_type_replenishment(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    text = get_text(user.language, 'profile_messages','Select the desired services for replenishment')
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        image_key='show_all_services_replenishments',
        reply_markup=await type_replenishment_kb(user.language)
    )


@router.callback_query(F.data.startswith('replenishment:'))
async def get_amount(callback: CallbackQuery, state: FSMContext, user: Users):
    payment_id = int(callback.data.split(':')[1])
    type_payment = await get_type_payment(payment_id)
    name_payment = callback.data.split(':')[2]

    if not type_payment or not type_payment.is_active:
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(user.language, 'profile_messages',"This services is temporarily inactive"),
            image_key='incorrect_data_entered',
            reply_markup=await type_replenishment_kb(user.language)
        )
        return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, 'profile_messages','{name_payment}. Enter the top-up amount in rubles').format(name_payment=name_payment),
        image_key='request_enter_amount',
        reply_markup=back_in_type_replenishment_kb(user.language)
    )

    await state.set_state(GetAmount.amount)
    await state.update_data(
        payment_id=type_payment.type_payment_id,
    )


@router.message(GetAmount.amount)
async def start_replenishment(message: Message, state: FSMContext, user: Users):
    data_state = await state.get_data()

    if not await checking_correctness_number(
            message=message.text,
            language=user.language,
            user_id=user.user_id,
            positive=True,
            reply_markup=back_in_type_replenishment_kb(user.language)
    ):
        await state.set_state(GetAmount.amount)
        return

    user_data = GetAmountData(
        amount=int(message.text),
        payment_id=data_state['payment_id'],
    )
    type_payment = await get_type_payment(user_data.payment_id)
    if not type_payment or not type_payment.is_active:
        await send_message(
            chat_id=message.from_user.id,
            message=get_text(user.language, 'profile_messages',"This services is temporarily inactive"),
            image_key=None,
            reply_markup=await type_replenishment_kb(user.language)
        )
        return

    total_amount = user_data.amount * type_payment.commission // 100 if type_payment.commission else user_data.amount

    if (MIN_MAX_REPLENISHMENT[type_payment.name_for_admin]['min'] > total_amount or
        MIN_MAX_REPLENISHMENT[type_payment.name_for_admin]['max'] < total_amount):
        text = get_text(
            user.language,
            'profile_messages',
            "Incorrect amount entered. \n\nMaximum: {amount_max} \nMinimum: {amount_min}"
        ).format(
            amount_max=MIN_MAX_REPLENISHMENT[type_payment.name_for_admin]['max'],
            amount_min=MIN_MAX_REPLENISHMENT[type_payment.name_for_admin]['min']
        )
        await send_message(
            chat_id=message.from_user.id,
            message=text,
            image_key='incorrect_data_entered',
            reply_markup=back_in_type_replenishment_kb(user.language)
        )
        return

    try:
        if type_payment.name_for_admin == 'crypto_bot':
            url = await crypto_bot.create_invoice(
                user_id=user.user_id,
                type_payment_id=type_payment.type_payment_id,
                origin_amount_rub=user_data.amount,
                amount_rub=total_amount
            )
        elif type_payment.name_for_admin == 'zelenka':
            pass
            # вызываем функцию для другого типа оплаты
            # вызываем функцию для другого типа оплаты
            # вызываем функцию для другого типа оплаты
            url = "example_url"
        else:
            await send_message(
                chat_id=message.from_user.id,
                message=get_text(user.language, 'profile_messages',"This services is temporarily inactive"),
                image_key=None,
                reply_markup=await type_replenishment_kb(user.language)
            )
            return

        text = n_get_text(
            user.language,
            'profile_messages',
            "{service_name}. Invoice successfully created. You have {minutes} minute to "
            "pay. After the time expires, the invoice will be canceled. \n\n"
            "Amount: {origin_sum}\n"
            "Payable: {total_sum} ₽ ( + commission {percent}%)",
            "{service_name}. Invoice successfully created. You have {minutes} minutes to "
            "pay. After the time expires, the invoice will be canceled. \n\n"
            "Amount: {origin_sum}\n"
            "Payable: {total_sum} ₽ ( + commission {percent}%)",
            PAYMENT_LIFETIME_SECONDS // 60
        ).format(
            service_name=type_payment.name_for_user,
            minutes=PAYMENT_LIFETIME_SECONDS // 60,
            origin_sum=user_data.amount,
            total_sum=total_amount,
            percent=type_payment.commission
        )

        await send_message(
            chat_id=message.from_user.id,
            message=text,
            image_key='pay',
            reply_markup=payment_invoice(user.language, url)
        )
    except Exception:
        text = get_text(user.language, 'profile_messages', "An error occurred, please try again")
        await send_message(
            chat_id=message.from_user.id,
            message=text,
            image_key='server_error',
            reply_markup=back_in_type_replenishment_kb(user.language)
        )


