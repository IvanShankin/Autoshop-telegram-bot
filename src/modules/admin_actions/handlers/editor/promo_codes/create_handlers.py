from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.modules.admin_actions.keyboards import select_promo_code_type_kb, \
    back_in_start_creating_promo_code_kb, skip_number_activations_promo_or_in_start_kb, \
    skip_expire_at_promo_or_in_start_kb, in_show_admin_promo_kb
from src.modules.admin_actions.schemas import CreatePromoCodeData
from src.modules.admin_actions.state import CreatePromoCode
from src.services.database.discounts.actions import get_promo_code, create_promo_code
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion, safe_parse_datetime
from src.utils.i18n import get_text

router = Router()


async def show_incorrect_data(user: Users):
    await send_message(
        user.user_id,
        get_text(user.language, "miscellaneous","incorrect_value_entered"),
        reply_markup=back_in_start_creating_promo_code_kb(user.language)
    )
    return


async def show_get_number_of_activations(state: FSMContext, user: Users):
    await send_message(
        user.user_id,
        get_text(
            user.language,
            "admins_editor_promo_codes",
            "enter_allowed_number_of_activations"
        ),
        reply_markup=skip_number_activations_promo_or_in_start_kb(user.language)
    )
    await state.set_state(CreatePromoCode.get_number_of_activations)
    return


async def send_message_get_expire_at_date(state: FSMContext, user: Users):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_promo_codes",
            "enter_expiration_date"
        ),
        reply_markup=skip_expire_at_promo_or_in_start_kb(user.language)
    )
    await state.set_state(CreatePromoCode.get_expire_at)


async def send_message_get_min_order_amount(state: FSMContext, user: Users):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_promo_codes",
            "enter_minimum_purchase_amount"
        ),
        reply_markup=back_in_start_creating_promo_code_kb(user.language)
    )
    await state.set_state(CreatePromoCode.get_min_order_amount)


async def send_message_get_code(state: FSMContext, user: Users):
    await send_message(
        chat_id=user.user_id,
        message=get_text(
            user.language,
            "admins_editor_promo_codes",
            "enter_activation_code"
        ),
        reply_markup=back_in_start_creating_promo_code_kb(user.language)
    )
    await state.set_state(CreatePromoCode.get_activation_code)


@router.callback_query(F.data == "admin_create_promo")
async def admin_create_promo_code(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_promo_codes",
            "select_promo_code_type"
        ),
        reply_markup=select_promo_code_type_kb(user.language)
    )


@router.callback_query(F.data == "create_promo_code_amount")
async def create_promo_code_amount(callback: CallbackQuery, state: FSMContext, user: Users):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_promo_codes",
            "enter_promo_code_discount_amount"
        ),
        reply_markup=back_in_start_creating_promo_code_kb(user.language)
    )
    await state.set_state(CreatePromoCode.get_amount)


@router.message(CreatePromoCode.get_amount)
async def create_promo_get_amount(message: Message, state: FSMContext, user: Users):
    amount = safe_int_conversion(message.text, positive=True)
    if not amount:
        await show_incorrect_data(user)
        return

    await state.update_data(amount=amount)
    await show_get_number_of_activations(state, user)


@router.callback_query(F.data == "create_promo_code_percentage")
async def create_promo_code_percentage(callback: CallbackQuery, state: FSMContext, user: Users):
    await edit_message(
        chat_id=user.user_id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "admins_editor_promo_codes",
            "enter_promo_code_discount_percentage"
        ),
        reply_markup=back_in_start_creating_promo_code_kb(user.language)
    )
    await state.set_state(CreatePromoCode.get_discount_percentage)


@router.message(CreatePromoCode.get_discount_percentage)
async def create_promo_get_get_discount_percentage(message: Message, state: FSMContext, user: Users):
    persent = safe_int_conversion(message.text, positive=True)
    if not persent:
        await show_incorrect_data(user)
        return
    if persent > 100:
        await send_message(
            chat_id=user.user_id,
            message=get_text(
                user.language,
                "admins_editor_promo_codes",
                "percentage_should_not_exceed_100"
            ),
            reply_markup=back_in_start_creating_promo_code_kb(user.language)
        )
        return

    await state.update_data(discount_percentage=persent)
    await show_get_number_of_activations(state, user)


@router.message(CreatePromoCode.get_number_of_activations)
async def create_promo_get_number_of_activations(message: Message, state: FSMContext, user: Users):
    number_of_activations = safe_int_conversion(message.text, positive=True)
    if not number_of_activations:
        await show_incorrect_data(user)
        return

    await state.update_data(number_of_activations=number_of_activations)
    await send_message_get_expire_at_date(state, user)


@router.callback_query(F.data == "set_expire_at_promo")
async def set_expire_at_promo(callback: CallbackQuery, state: FSMContext, user: Users):
    """Если попали в такой handler, значит пользователь пропустил число активаций"""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await send_message_get_expire_at_date(state, user)


@router.message(CreatePromoCode.get_expire_at)
async def get_expire_at(message: Message, state: FSMContext, user: Users):
    expire_at = safe_parse_datetime(message.text)
    if not expire_at:
        await show_incorrect_data(user)
        return

    await state.update_data(expire_at=expire_at)
    await send_message_get_min_order_amount(state, user)


@router.callback_query(F.data == "set_min_order_amount_promo")
async def set_min_order_amount_promo(callback: CallbackQuery, state: FSMContext, user: Users):
    """Если попали в такой handler, значит пользователь пропустил срок годности промокода"""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await send_message_get_min_order_amount(state, user)


@router.message(CreatePromoCode.get_min_order_amount)
async def get_min_order_amount(message: Message, state: FSMContext, user: Users):
    min_order_amount = safe_int_conversion(message.text)
    if not min_order_amount:
        await show_incorrect_data(user)
        return

    await state.update_data(min_order_amount=min_order_amount)
    await send_message_get_code(state, user)


@router.message(CreatePromoCode.get_activation_code)
async def get_activation_code(message: Message, state: FSMContext, user: Users):
    if len(message.text) > 150:
        text = get_text(
            user.language,
            "admins_editor_promo_codes",
            "code_length_exceeded"
        )
        reply_markup = back_in_start_creating_promo_code_kb(user.language)
    elif await get_promo_code(code=message.text):
        text = get_text(
            user.language,
            "admins_editor_promo_codes",
            "code_already_taken"
        )
        reply_markup = back_in_start_creating_promo_code_kb(user.language)
    else:

        data = CreatePromoCodeData(**(await state.get_data()))
        try:
            new_promo_code = await create_promo_code(
                creator_id=user.user_id,
                code=message.text,
                min_order_amount=data.min_order_amount,
                amount=data.amount,
                discount_percentage=data.discount_percentage,
                number_of_activations=data.number_of_activations,
                expire_at=data.expire_at
            )
            text = get_text(
                user.language,
                "admins_editor_promo_codes",
                "promo_code_successfully_created"
            )
            reply_markup = in_show_admin_promo_kb(
                user.language,
                current_page=1,
                promo_code_id=new_promo_code.promo_code_id,
                show_not_valid=False
            )
        except Exception:
            text = get_text(
                user.language,
                "admins_editor_promo_codes",
                "unable_to_create_promo_code"
            )
            reply_markup = back_in_start_creating_promo_code_kb(user.language)

    await send_message(
        chat_id=user.user_id,
        message=text,
        reply_markup=reply_markup
    )