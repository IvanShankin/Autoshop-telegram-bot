from typing import Callable, Coroutine, Any

from aiogram.types import CallbackQuery

from src.bot_actions.bot_instance import get_bot
from src.bot_actions.messages import edit_message, send_message
from src.exceptions import InvalidPromoCode, CategoryNotFound, NotEnoughMoney, NotEnoughAccounts
from src.exceptions.business import NotEnoughProducts
from src.modules.categories.keyboards import replenishment_and_back_in_cat, back_in_account_category_kb
from src.modules.categories.services.helpers import check_category
from src.modules.profile.keyboards import in_profile_kb
from src.services.database.categories.actions import purchase
from src.services.database.categories.models import CategoryFull
from src.services.database.discounts.utils.calculation import discount_calculation
from src.services.database.users.models import Users
from src.utils.i18n import get_text


async def _show_not_enough_money(
    need_money: int,
    category_id: int,
    quantity_products: int,
    callback: CallbackQuery,
    user: Users
):
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, 'miscellaneous', "Insufficient funds: {amount}").format(amount=need_money),
        image_key='insufficient_funds',
        fallback_image_key="default_catalog_account",
        reply_markup=replenishment_and_back_in_cat(
            language=user.language,
            category_id=category_id,
            quantity_for_buying=quantity_products,
        )
    )


async def _show_no_enough_products(
    callback: CallbackQuery,
    user: Users
):
    await callback.answer(
        get_text(
            user.language,
            'categories',
            "There are not enough products on the server, please change the number of accounts to purchase"
        ),
        show_alert=True
    )


async def _buy(
    user: Users,
    callback: CallbackQuery,
    delete_message_def: Callable[[], Coroutine[Any, Any, Any]],
    category: CategoryFull,
    promo_code_id: int,
    quantity_products: int,
):
    try:
        result = await purchase(
            user_id=user.user_id,
            category_id=category.category_id,
            quantity_products=quantity_products,
            promo_code_id=promo_code_id,
            product_type=category.product_type,
            language=user.language
        )
    except (NotEnoughAccounts, NotEnoughProducts ):
        await delete_message_def()
        await _show_no_enough_products(
            callback=callback,
            user=user
        )
        return


    await delete_message_def()

    if result is True:
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(user.language, 'categories',
                             "Thank you for your purchase \nThe account is already in the profile"),
            image_key='successful_purchase',
            fallback_image_key="default_catalog_account",
            reply_markup=in_profile_kb(language=user.language)
        )
    else:
        # тут будем если нашли невалидные аккаунты и не смогли найти замену им
        get_text(
            user.language,
            'categories',
            "There are not enough products on the server, please change the number of accounts to purchase"
        ),
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                'categories',
                "There are not enough products on the server, please change the number of accounts to purchase"
            ),
            image_key='successful_purchase',
            fallback_image_key="default_catalog_account",
            reply_markup=back_in_account_category_kb(
                language=user.language,
                category_id=category.category_id,
                quantity_for_buying=quantity_products,
            )
        )


async def buy_product(
    category_id: int,
    promo_code_id: int | None,
    quantity_products: int,
    callback: CallbackQuery,
    user: Users,
):

    category = await check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    # если на сервере недостаточно продуктов
    if category.quantity_product < quantity_products:
        await _show_no_enough_products(
            callback=callback,
            user=user
        )
        return

    total_sum = category.price * quantity_products

    if promo_code_id is not None:  # если есть promo_code_id
        try:
            discount_sum, promo_code = await discount_calculation(amount=total_sum, promo_code_id=promo_code_id)
            total_sum = max(0, total_sum - discount_sum)

            # если минимальная сумма активации промокода не достигнута
            if promo_code and promo_code.min_order_amount > total_sum:
                await callback.answer(
                    get_text(
                        user.language,
                        'discount',
                        "Purchase not processed! \n"
                        "Minimum amount to apply the promo code: {amount}"
                    ).format(amount=promo_code.min_order_amount),
                    show_alert=True
                )
                return
        except InvalidPromoCode:
            await callback.answer(
                get_text(
                    user.language,
                    'discount',
                    "Attention, the promo code is no longer valid, the discount will no longer apply!"),
                show_alert=True
            )
            return

    # если недостаточно средств
    if user.balance < total_sum:
        await _show_not_enough_money(
            total_sum - user.balance,
            category_id=category_id,
            quantity_products=quantity_products,
            callback=callback,
            user=user
        )
        return

    message_load = await send_message(user.user_id, get_text(user.language,'categories',"Test products..."))
    async def delete_message():
        try:
            await message_load.delete()
        except Exception:
            pass

    try:
        await _buy(
            user=user,
            callback=callback,
            delete_message_def=delete_message,
            category=category,
            promo_code_id=promo_code_id,
            quantity_products=quantity_products
        )

    except CategoryNotFound as e:
        await delete_message()
        try:
            bot = await get_bot()
            await bot.delete_message(user.user_id, callback.message.message_id)
        except Exception:
            pass

        await send_message(
            chat_id=user.user_id,
            message=get_text(user.language, 'categories',"The category is temporarily unavailable"),
        )
        return
    except NotEnoughMoney as e:
        await delete_message()
        await _show_not_enough_money(
            e.need_money,
            category_id=category_id,
            quantity_products=quantity_products,
            callback=callback,
            user=user
        )
        return

