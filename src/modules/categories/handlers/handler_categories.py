import asyncio

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.exceptions import InvalidPromoCode
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.categories.keyboards import subscription_prompt_kb, back_in_account_category_kb, confirm_buy_kb, \
    main_categories_kb
from src.modules.categories.services import check_category, edit_message_category, buy_product
from src.modules.categories.shemas import BuyProductsData
from src.modules.categories.states import BuyProduct
from src.modules.keyboard_main import support_kb
from src.services.database.categories.actions import get_categories
from src.services.database.discounts.actions import get_promo_code
from src.services.database.discounts.actions.actions_promo import check_activate_promo_code
from src.services.database.discounts.utils.calculation import discount_calculation
from src.services.database.users.models import Users
from src.services.redis.actions import delete_subscription_prompt, get_subscription_prompt
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text

router_with_repl_kb = Router()
router = Router()


@router_with_repl_kb.message(I18nKeyFilter("Product categories"))
async def handle_catalog_message(message: Message, state: FSMContext, user: Users):
    await state.clear()

    if await get_subscription_prompt(user.user_id): # если пользователю ранее не предлагали подписаться
        await send_message(
            chat_id=user.user_id,
            message=get_text(
                user.language,
                'categories',
                'Want to stay up-to-date on all the latest news? \n'
                'Subscribe to our channel where we share news and special offers'
            ),
            image_key='subscription_prompt',
            reply_markup=await subscription_prompt_kb(user.language)
        )
        return

    await message_in_main_category(user)


async def message_in_main_category(user: Users, old_message_id: int | None = None):
    """
    :param user: пользователь
    :param old_message_id: если указать, то сообщение с данным id будет отредактировано, иначе отправится новое
    """

    if not await get_categories(language=user.language):
        await send_message(
            chat_id=user.user_id,
            message=get_text(user.language, "categories", "There are no categories at the moment"),
            reply_markup=await support_kb(user.language)
        )
        return

    if old_message_id:
        await edit_message(
            message_id=old_message_id,
            chat_id=user.user_id,
            image_key='main_category',
            fallback_image_key="default_catalog_account",
            reply_markup=await main_categories_kb(user.language)
        )
        return

    await send_message(
        chat_id=user.user_id,
        image_key='main_category',
        fallback_image_key="default_catalog_account",
        reply_markup=await main_categories_kb(user.language)
    )


@router.callback_query(F.data == "skip_subscription")
async def skip_subscription(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await delete_subscription_prompt(callback.from_user.id) # больше не просим подписаться

    await message_in_main_category(
        user=user,
        old_message_id=callback.message.message_id
    )


@router.callback_query(F.data == "show_main_categories")
async def show_main_categories(callback: CallbackQuery, state: FSMContext, user: Users):
    await state.clear()
    await message_in_main_category(
        user=user,
        old_message_id=callback.message.message_id
    )


@router.callback_query(F.data.startswith("show_category:"))
async def show_category(callback: CallbackQuery, state: FSMContext, user: Users):
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

    if category.is_product_storage:
        # попадём сюда если пользователь произвёл действия на категории, где хранятся аккаунты

        # если имеется меньше, чем хочет пользователь и у категории нельзя переиспользовать продукт
        if category.quantity_product < quantity_products and not category.reuse_product:
            await callback.answer(get_text(user.language, 'categories','No longer in stock'))
            return
        if quantity_products < 0:
            await callback.answer('')  # что бы не весело сообщение
            return

        # обновление данных в состоянии
        data = BuyProductsData(**(await state.get_data()))
        data.quantity_for_buying = quantity_products
        data.old_message_id = callback.message.message_id
        data.category_id = category_id

        await state.update_data(**data.model_dump())
        await state.set_state(BuyProduct.quantity_products)
    else:
        # если пользователь перемещается оп категориям (так же может выйти назад с категории)
        await state.clear()
        data = BuyProductsData(old_message_id=callback.message.message_id, category_id=category.category_id)
        await state.update_data(**data.model_dump())

    await edit_message_category(
        user=user,
        message_id=callback.message.message_id,
        data=data,
        category=category
    )


@router.message(BuyProduct.quantity_products)
async def set_quantity_products(message: Message, state: FSMContext, user: Users):
    try:
        await message.delete()
    except Exception:
        pass # если пользователь удалил сам

    data = BuyProductsData(**(await state.get_data()))

    category = await check_category(
        category_id=data.category_id,
        old_message_id=data.old_message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    new_quantity_products = safe_int_conversion(value=message.text, default=None, positive=True)
    sent_message = None
    if new_quantity_products is None:
        sent_message = await send_message(user.user_id, get_text(user.language, 'miscellaneous',"Incorrect value entered. Please try again"))
    elif new_quantity_products > category.quantity_product:
        sent_message = await send_message(user.user_id, get_text(user.language, 'categories',"No longer in stock"))
    else:
        data.quantity_for_buying = new_quantity_products
        await state.update_data(**data.model_dump())

    await state.set_state(BuyProduct.quantity_products)

    if sent_message: # удаление старого сообщения о некорректном значении
        await asyncio.sleep(3)
        try:
            await sent_message.delete()
        except Exception:
            pass  # если пользователь удалил сам
        return


    await edit_message_category(
        user=user,
        message_id=data.old_message_id,
        data=data,
        category=category
    )


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
        message=get_text(user.language, 'categories',"Enter the activation code"),
        image_key='entering_promo_code',
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
            message=get_text(user.language, 'discount',"A promo code with this code was not found/expired \n\nTry again"),
            image_key='entering_promo_code',
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
            message=get_text(user.language, 'discount',"This promo code has already been activated previously \n\nTry again"),
            image_key='entering_promo_code',
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

    promo_message = await send_message(user.user_id, 'The promo code has been successfully activated')
    await asyncio.sleep(3)
    try:
        await promo_message.delete()
    except Exception:
        pass  # если пользователь удалил сам
    return


@router.callback_query(F.data.startswith('confirm_buy_category:'))
async def confirm_buy_category(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    quantity_products = int(callback.data.split(':')[2]) # число аккаунтов на приобретение
    promo_code_id = safe_int_conversion(callback.data.split(':')[3], positive=True) # либо int, либо "None"

    if quantity_products <= 0:
        await callback.answer(get_text(user.language, 'categories',"Select at least one product"))
        return

    category = await check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    total_sum = category.price * quantity_products

    if promo_code_id is not None: # если есть promo_code_id
        try:
            discount_sum, _ = await discount_calculation(amount=total_sum, promo_code_id=promo_code_id)
            total_sum = max(0, total_sum - discount_sum)
        except InvalidPromoCode:
            await callback.answer(
                get_text(
                    user.language,
                    'discount',
                    "Attention, the promo code is no longer valid, the discount will no longer apply!"
                ),
                show_alert=True
            )
            return

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            'categories',
            "Confirm your purchase\n\n"
            "{category_name}\n"
            "Product will be received: {quantity_products}\n"
            "Your balance: {balance}\n"
            "Due: {total_sum}"
        ).format(
            category_name=category.name,
            quantity_products=quantity_products,
            balance=user.balance,
            total_sum=total_sum
        ),
        image_key = 'confirm_purchase',
        fallback_image_key = "default_catalog_account",
        reply_markup=confirm_buy_kb(
            language=user.language,
            category_id=category_id,
            quantity_for_buying=quantity_products,
            promo_code_id=promo_code_id
        )
    )


@router.callback_query(F.data.startswith('buy_in_category:'))
async def buy_in_category(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    quantity_products = int(callback.data.split(':')[2])  # число продуктов на приобретение
    promo_code_id = safe_int_conversion(callback.data.split(':')[3], positive=True)  # либо int, либо "None"

    await buy_product(
        category_id=category_id,
        promo_code_id=promo_code_id,
        quantity_products=quantity_products,
        callback=callback,
        user=user,
    )
    await state.clear()