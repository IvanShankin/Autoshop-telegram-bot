import asyncio

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src._bot_actions.messages import edit_message, send_message
from src.application._database.discounts.actions import get_promo_code
from src.application._database.discounts.actions.actions_promo import check_activate_promo_code
from src.database.models.users import Users
from src.modules.categories.keyboards import back_in_account_category_kb
from src.modules.categories.services import check_category, edit_message_category
from src.modules.categories.shemas import BuyProductsData
from src.modules.categories.states import BuyProduct
from src.utils.i18n import get_text

router_with_repl_kb = Router()
router = Router()


@router.callback_query(F.data.startswith('enter_promo:'))
async def enter_promo(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    quantity_products = int(callback.data.split(':')[2]) # число аккаунтов на приобретение

    category = await check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "categories","enter_activation_code"),
        event_message_key='entering_promo_code',
        reply_markup=back_in_account_category_kb(
            user.language,
            category_id=category.category_id,
            quantity_for_buying=quantity_products
        )
    )

    await state.set_state(BuyProduct.promo_code)
    await state.update_data(old_message_id=callback.message.message_id)


@router.message(BuyProduct.promo_code)
async def set_promo_code(message: Message, state: FSMContext, user: Users):
    try:
        await message.delete()
    except Exception:
        pass

    promo = await get_promo_code(message.text)
    data = BuyProductsData(**(await state.get_data()))

    category = await check_category(
        category_id=data.category_id,
        old_message_id=data.old_message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    if not promo:
        await edit_message(
            chat_id=message.from_user.id,
            message_id=data.old_message_id,
            message=get_text(user.language, "discount","promo_code_not_found_or_expired"),
            event_message_key='entering_promo_code',
            reply_markup=back_in_account_category_kb(
                user.language,
                category_id=data.category_id,
                quantity_for_buying=data.quantity_for_buying
            )
        )
        await state.set_state(BuyProduct.promo_code)
        return

    # если активирован ранее
    if await check_activate_promo_code(promo_code_id=promo.promo_code_id, user_id=user.user_id):
        await edit_message(
            chat_id=message.from_user.id,
            message_id=data.old_message_id,
            message=get_text(user.language, "discount","promo_code_already_activated"),
            event_message_key='entering_promo_code',
            reply_markup=back_in_account_category_kb(
                user.language,
                category_id=data.category_id,
                quantity_for_buying=data.quantity_for_buying
            )
        )
        await state.set_state(BuyProduct.promo_code)
        return

    await state.update_data(
        promo_code_id = promo.promo_code_id,
        promo_code = promo.activation_code,
        promo_code_amount = promo.amount,
        discount_percentage = promo.discount_percentage,
    )

    await edit_message_category(
        user = user,
        message_id = data.old_message_id,
        data = BuyProductsData(**(await state.get_data())),
        category = category
    )

    promo_message = await send_message(
        user.user_id,
        get_text(user.language, "discount", "promo_code_successfully_activated")
    )
    await asyncio.sleep(3)
    try:
        await promo_message.delete()
    except Exception:
        pass  # если пользователь удалил сам
    return

