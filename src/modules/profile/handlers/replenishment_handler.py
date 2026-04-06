from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.database.models.system.models import ReplenishmentService
from src.models.read_models import UsersDTO
from src.modules.profile.services.checking_data import checking_correctness_number
from src.modules.profile.keyboards import type_replenishment_kb, back_in_type_replenishment_kb, payment_invoice
from src.modules.profile.schemas.replenishment import GetAmountData
from src.modules.profile.state.replenishment import GetAmount
from src.services.bot import Messages
from src.services.models.module import ProfileModule
from src.utils.i18n import get_text, n_get_text

router_with_repl_kb = Router()
router = Router()


@router.callback_query(F.data == "show_type_replenishment")
async def show_type_replenishment(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    await state.clear()
    text = get_text(user.language, "profile_messages",'select_replenishment_service')
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=text,
        event_message_key='show_all_services_replenishments',
        reply_markup=await type_replenishment_kb(user.language, profile_module)
    )


@router.callback_query(F.data.startswith('replenishment:'))
async def get_amount(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, profile_module: ProfileModule, messages_service: Messages
):
    payment_id = int(callback.data.split(':')[1])
    type_payment = await profile_module.type_payments_service.get_type_payment(payment_id)
    name_payment = callback.data.split(':')[2]

    if not type_payment or not type_payment.is_active:
        await messages_service.edit_msg.edit(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(user.language, "profile_messages","service_temporarily_inactive"),
            event_message_key='incorrect_data_entered',
            reply_markup=await type_replenishment_kb(user.language, profile_module)
        )
        return

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "profile_messages",'enter_top_up_amount').format(name_payment=name_payment),
        event_message_key='request_enter_amount',
        reply_markup=back_in_type_replenishment_kb(user.language)
    )

    await state.set_state(GetAmount.amount)
    await state.update_data(
        payment_id=type_payment.type_payment_id,
    )


@router.message(GetAmount.amount)
async def start_replenishment(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages, profile_module: ProfileModule,
):
    data_state = await state.get_data()

    if not await checking_correctness_number(
        message=message.text,
        language=user.language,
        user_id=user.user_id,
        positive=True,
        reply_markup=back_in_type_replenishment_kb(user.language),
        messages_service=messages_service
    ):
        await state.set_state(GetAmount.amount)
        return

    user_data = GetAmountData(
        amount=int(message.text),
        payment_id=data_state['payment_id'],
    )
    type_payment = await profile_module.type_payments_service.get_type_payment(user_data.payment_id)
    if not type_payment or not type_payment.is_active:
        await messages_service.send_msg.send(
            chat_id=message.from_user.id,
            message=get_text(user.language, "profile_messages","service_temporarily_inactive"),
            reply_markup=await type_replenishment_kb(user.language, profile_module)
        )
        return

    total_amount = await profile_module.type_payments_service.calculate_replenishment_amount(
        amount=user_data.amount, type_payment=type_payment
    )

    if (profile_module.conf.app.min_max_replenishment[type_payment.service.value]['min'] > total_amount or
        profile_module.conf.app.min_max_replenishment[type_payment.service.value]['max'] < total_amount):
        text = get_text(
            user.language,
            "profile_messages",
            "incorrect_amount_entered"
        ).format(
            amount_max=profile_module.conf.app.min_max_replenishment[type_payment.service.value]['max'],
            amount_min=profile_module.conf.app.min_max_replenishment[type_payment.service.value]['min']
        )
        await messages_service.send_msg.send(
            chat_id=message.from_user.id,
            message=text,
            event_message_key="incorrect_data_entered",
            reply_markup=back_in_type_replenishment_kb(user.language)
        )
        return

    try:
        if type_payment.service == ReplenishmentService.CRYPTO_BOT:
            url = await profile_module.payment_service.create(
                user_id=user.user_id,
                type_payment_id=type_payment.type_payment_id,
                origin_amount_rub=user_data.amount,
                amount_rub=total_amount,
                service=type_payment.service,
            )
        else:
            await messages_service.send_msg.send(
                chat_id=message.from_user.id,
                message=get_text(user.language, "profile_messages","service_temporarily_inactive"),
                reply_markup=await type_replenishment_kb(user.language, profile_module)
            )
            return

        text = n_get_text(
            user.language,
            "profile_messages",
            "invoice_successfully_created",
            "invoice_successfully_created",
            profile_module.conf.different.payment_lifetime_seconds // 60
        ).format(
            service_name=type_payment.name_for_user,
            minutes=profile_module.conf.different.payment_lifetime_seconds // 60,
            origin_sum=user_data.amount,
            total_sum=total_amount,
            percent=type_payment.commission
        )

        await messages_service.send_msg.send(
            chat_id=message.from_user.id,
            message=text,
            event_message_key='pay',
            reply_markup=payment_invoice(user.language, url)
        )
    except Exception as e:
        profile_module.logger.exception("Ошибка при попытки дать пользователю данные на оплату")
        text = get_text(user.language, "miscellaneous", "an_error_occurred")
        await messages_service.send_msg.send(
            chat_id=message.from_user.id,
            message=text,
            event_message_key='server_error',
            reply_markup=back_in_type_replenishment_kb(user.language)
        )

    await state.clear()


