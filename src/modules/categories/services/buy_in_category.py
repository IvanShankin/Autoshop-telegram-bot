from typing import Callable, Coroutine, Any

from aiogram.types import CallbackQuery

from src.bot_actions.bot_instance import get_bot
from src.bot_actions.messages import edit_message, send_message, like_with_heart
from src.exceptions import InvalidPromoCode, CategoryNotFound, NotEnoughMoney, NotEnoughAccounts
from src.exceptions.business import NotEnoughProducts
from src.modules.categories.keyboards import replenishment_and_back_in_cat, back_in_account_category_kb
from src.modules.categories.services.helpers import check_category
from src.modules.profile.keyboards import in_purchased_account_kb, in_purchased_universal_product_kb
from src.services.database.categories.actions import purchase
from src.services.database.categories.actions.products.accounts.actions_get import get_sold_accounts_by_owner_id
from src.services.database.categories.actions.products.universal.actions_get import get_sold_universal_by_owner_id
from src.services.database.categories.models import CategoryFull, ProductType
from src.services.database.discounts.utils.calculation import discount_calculation
from src.services.database.users.models import Users
from src.utils.i18n import get_text, n_get_text


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
    except (NotEnoughAccounts, NotEnoughProducts):
        await delete_message_def()
        await _show_no_enough_products(
            callback=callback,
            user=user
        )
        return


    await delete_message_def()

    if result is True:
        reply_markup = None
        if category.product_type == ProductType.ACCOUNT:
            sold_account_id = None

            if quantity_products == 1:
                all_sold_acc = await get_sold_accounts_by_owner_id(user.user_id, user.language)
                if all_sold_acc:
                    sold_account_id = all_sold_acc[0].sold_account_id

            reply_markup = in_purchased_account_kb(
                language=user.language,
                quantity_products=quantity_products,
                sold_account_id=sold_account_id,
                type_account_service=category.type_account_service
            )
        elif category.product_type == ProductType.UNIVERSAL:
            sold_universal_id = None

            if quantity_products == 1:
                all_sold_uni = await get_sold_universal_by_owner_id(user.user_id, user.language)
                if all_sold_uni:
                    sold_universal_id = all_sold_uni[0].sold_universal_id

            reply_markup = in_purchased_universal_product_kb(
                language=user.language,
                quantity_products=quantity_products,
                sold_universal_id=sold_universal_id,
            )

        try:
            await callback.message.delete()
        except:
            pass

        await send_message(
            chat_id=callback.from_user.id,
            message=n_get_text(
                user.language,
                'categories',
                "Thank you for your purchase \nThe product is already in the profile",
                "Thank you for your purchase \nThe product is already in the profile",
                quantity_products
            ),
            image_key='successful_purchase',
            fallback_image_key="default_catalog_account",
            reply_markup=reply_markup,
            message_effect_id="5159385139981059251"
        )
    else:
        # тут будем если нашли невалидные аккаунты и не смогли найти замену им
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

    # если на сервере недостаточно продуктов и их нельзя переиспользовать
    if category.quantity_product < quantity_products and not category.reuse_product:
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

