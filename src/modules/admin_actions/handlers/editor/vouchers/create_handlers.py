from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.bot_instance import get_bot
from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards.vouchers_kb import skip_number_activations_or_back_kb, \
    back_in_start_creating_admin_vouchers_kb, skip_expire_at_or_back_kb, in_admin_voucher_kb
from src.modules.admin_actions.schemas.editor_vouchers import CreateAdminVoucherData
from src.modules.admin_actions.state.editor_vouchers import CreateAdminVoucher
from src.services.database.discounts.actions import create_voucher
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion, safe_parse_datetime
from src.utils.i18n import get_text

router = Router()


async def send_message_get_expire_at_date(state: FSMContext, user: Users):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "Enter the date until which the voucher will be valid. With Moscow time zone (local time in Moscow)\n"
            "If you click skip, the voucher will be valid indefinitely."
            "\n\nExample: <code>2025-12-02 16:42:57</code>"
        ),
        reply_markup=skip_expire_at_or_back_kb(user.language)
    )
    await state.set_state(CreateAdminVoucher.expire_at)


async def send_message_get_amount(state: FSMContext, user: Users):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "Enter the amount the user receives when activating the voucher"
        ),
        reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
    )
    await state.set_state(CreateAdminVoucher.amount)


@router.callback_query(F.data == "admin_create_voucher")
async def admin_create_voucher(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "Enter the allowed number of voucher activations \n"
            "If you click skip, the number will be unlimited \n\n"
            "Note: Each user can only activate once"
        ),
        reply_markup=skip_number_activations_or_back_kb(user.language)
    )
    await state.set_state(CreateAdminVoucher.number_of_activations)


@router.message(CreateAdminVoucher.number_of_activations)
async def get_number_of_activations(message: Message, state: FSMContext, user: Users):
    number_of_activations = safe_int_conversion(message.text, positive=True)
    if not number_of_activations:
        await send_message(
            user.user_id,
            get_text(user.language, 'miscellaneous',"Incorrect value entered"),
            reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
        )
        return

    await state.update_data(number_of_activations=number_of_activations)
    await send_message_get_expire_at_date(state, user)


@router.callback_query(F.data == "set_expire_at")
async def set_expire_at(callback: CallbackQuery, state: FSMContext, user: Users):
    """Если попали в такой handler, значит пользователь пропустил число активаций"""
    await state.clear()
    await send_message_get_expire_at_date(state, user)


@router.message(CreateAdminVoucher.expire_at)
async def get_expire_at(message: Message, state: FSMContext, user: Users):
    expire_at = safe_parse_datetime(message.text)
    if not expire_at:
        await send_message(
            user.user_id,
            get_text(user.language, 'miscellaneous', "Incorrect value entered"),
            reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
        )
        return

    await state.update_data(expire_at=expire_at)
    await send_message_get_amount(state, user)


@router.callback_query(F.data == "set_amount_admin_voucher")
async def set_amount_admin_voucher(callback: CallbackQuery, state: FSMContext, user: Users):
    """Если попали в такой handler, значит пользователь пропустил срок годности ваучера"""
    await send_message_get_amount(state, user)


@router.message(CreateAdminVoucher.amount)
async def get_amount(message: Message, state: FSMContext, user: Users):
    amount = safe_int_conversion(message.text, positive=True)
    if not amount:
        await send_message(
            user.user_id,
            get_text(user.language, 'miscellaneous',"Incorrect value entered"),
            reply_markup=back_in_start_creating_admin_vouchers_kb(user.language)
        )
        return

    data = CreateAdminVoucherData(** (await state.get_data()))

    new_voucher = await create_voucher(
        user_id=user.user_id,
        is_created_admin=True,
        amount=amount,
        number_of_activations=data.number_of_activations,
        expire_at=data.expire_at
    )

    bot = await get_bot()
    bot_me = await bot.me()
    await send_message(
        user.user_id,
        message=get_text(
            user.language,
            "admins_editor_vouchers",
            "Voucher successfully created.\n\n"
            "ID: {id}\n"
            "Link: <a href='{link}'>Copy</a> \n"
            "Allowed number of activations: {number_of_activations}\n"
            "Amount of one voucher: {amount_one_voucher}\n"
            "Valid until: {expire_at}\n"
        ).format(
            id=new_voucher.voucher_id,
            link=f'https://t.me/{bot_me.username}?start=voucher_{new_voucher.activation_code}',
            number_of_activations=new_voucher.number_of_activations,
            amount_one_voucher=new_voucher.amount,
            expire_at=new_voucher.expire_at,
        ),
        reply_markup=in_admin_voucher_kb(user.language, 1, new_voucher.voucher_id )
    )
