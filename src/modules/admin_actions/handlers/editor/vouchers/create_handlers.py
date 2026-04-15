from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import AdminModule
from src.infrastructure.telegram.bot_client import TelegramClient
from src.models.create_models.discounts import CreateVoucherDTO
from src.models.read_models import UsersDTO
from src.modules.admin_actions.keyboards import skip_number_activations_or_back_kb, \
    back_in_start_creating_admin_vouchers_kb, skip_expire_at_or_back_kb, in_admin_voucher_kb
from src.modules.admin_actions.schemas import CreateAdminVoucherData
from src.modules.admin_actions.state import CreateAdminVoucher

from src.utils.converter import safe_int_conversion, safe_parse_datetime
from src.utils.i18n import get_text

router = Router()


async def send_message_get_expire_at_date(
    state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "enter_voucher_expiration_date"
        ),
        reply_markup=skip_expire_at_or_back_kb(user.language)
    )
    await state.set_state(CreateAdminVoucher.expire_at)


async def send_message_get_amount(
    state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await messages_service.send_msg.send(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "enter_voucher_amount"
        ),
        reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
    )
    await state.set_state(CreateAdminVoucher.amount)


@router.callback_query(F.data == "admin_create_voucher")
async def admin_create_voucher(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    await state.clear()
    await messages_service.edit_msg.edit(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "enter_allowed_number_of_voucher_activations"
        ),
        reply_markup=skip_number_activations_or_back_kb(user.language)
    )
    await state.set_state(CreateAdminVoucher.number_of_activations)


@router.message(CreateAdminVoucher.number_of_activations)
async def get_number_of_activations(
    message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    number_of_activations = safe_int_conversion(message.text, positive=True)
    if not number_of_activations:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language, "miscellaneous","incorrect_value_entered"),
            reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
        )
        return

    await state.update_data(number_of_activations=number_of_activations)
    await send_message_get_expire_at_date(state, user, messages_service=messages_service)


@router.callback_query(F.data == "set_expire_at")
async def set_expire_at(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    """Если попали в такой handler, значит пользователь пропустил число активаций"""
    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()
    await send_message_get_expire_at_date(state, user, messages_service=messages_service)


@router.message(CreateAdminVoucher.expire_at)
async def get_expire_at(message: Message, state: FSMContext, user: UsersDTO, messages_service: Messages,):
    expire_at = safe_parse_datetime(message.text)
    if not expire_at:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language, "miscellaneous", "incorrect_value_entered"),
            reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
        )
        return

    await state.update_data(expire_at=expire_at)
    await send_message_get_amount(state, user, messages_service=messages_service)


@router.callback_query(F.data == "set_amount_admin_voucher")
async def set_amount_admin_voucher(
    callback: CallbackQuery, state: FSMContext, user: UsersDTO, messages_service: Messages,
):
    """Если попали в такой handler, значит пользователь пропустил срок годности ваучера"""
    try:
        await callback.message.delete()
    except Exception:
        pass

    await send_message_get_amount(state, user, messages_service)


@router.message(CreateAdminVoucher.amount)
async def get_amount(
    message: Message,
    state: FSMContext,
    user: UsersDTO,
    admin_module: AdminModule,
    messages_service: Messages,
    tg_client: TelegramClient,
):
    amount = safe_int_conversion(message.text, positive=True)
    if not amount:
        await messages_service.send_msg.send(
            user.user_id,
            get_text(user.language, "miscellaneous","incorrect_value_entered"),
            reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
        )
        return

    data = CreateAdminVoucherData(** (await state.get_data()))

    new_voucher = await admin_module.voucher_service.create_voucher(
        user_id=user.user_id,
        data=CreateVoucherDTO(
            is_created_admin=True,
            amount=amount,
            number_of_activations=data.number_of_activations,
            expire_at=data.expire_at
        ),
    )

    bot_me = await tg_client.me()
    await messages_service.send_msg.send(
        user.user_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "voucher_successfully_created"
        ).format(
            id=new_voucher.voucher_id,
            link=f'https://t.me/{bot_me.username}?start=voucher_{new_voucher.activation_code}',
            number_of_activations=(
                new_voucher.number_of_activations
                if new_voucher.number_of_activations else
                get_text(user.language,"admins_editor_vouchers", "unlimited")
            ),
            amount_one_voucher=new_voucher.amount,
            expire_at=(
                new_voucher.expire_at
                if new_voucher.expire_at else
                get_text(user.language,"admins_editor_vouchers", "endlessly")
            )
        ),
        reply_markup=in_admin_voucher_kb(user.language, 1, new_voucher.voucher_id )
    )
