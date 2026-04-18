from typing import Callable, Coroutine, Any

from aiogram.types import CallbackQuery

from src.application.bot import Messages
from src.application.models.modules import CatalogModule
from src.exceptions import InvalidPromoCode, CategoryNotFound, NotEnoughMoney, NotEnoughAccounts
from src.exceptions.business import NotEnoughProducts
from src.infrastructure.telegram.bot_client import TelegramClient
from src.modules.categories.keyboards import replenishment_and_back_in_cat, back_in_account_category_kb
from src.modules.categories.services.helpers import check_category
from src.modules.profile.keyboards import in_purchased_account_kb, in_purchased_universal_product_kb
from src.database.models.categories import ProductType
from src.models.read_models import CategoryFull
from src.database.models.users import Users
from src.infrastructure.translations import get_text, n_get_text


async def _show_not_enough_money(
    need_money: int,
    category_id: int,
    quantity_products: int,
    callback: CallbackQuery,
    user: Users,
    messages_service: Messages,
):
    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(user.language, "miscellaneous", "insufficient_funds").format(amount=need_money),
        event_message_key='insufficient_funds',
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
            "categories",
            "not_enough_products_on_server"
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
    messages_service: Messages,
    catalog_modul: CatalogModule,
):
    try:
        result = await catalog_modul.purchase_service.purchase(
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
                all_sold_acc = await catalog_modul.account_sold_service.get_sold_accounts_by_owner_id(
                    user.user_id, user.language
                )
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
                all_sold_uni = await catalog_modul.universal_sold_service.get_sold_universal_by_owner_id(
                    user.user_id, user.language
                )
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

        await messages_service.send_msg.send(
            chat_id=callback.from_user.id,
            message=n_get_text(
                user.language,
                "categories",
                "thank_you_for_purchase",
                "thank_you_for_purchase",
                quantity_products
            ),
            event_message_key='successful_purchase',
            fallback_image_key="default_catalog_account",
            reply_markup=reply_markup,
            message_effect_id="5159385139981059251"
        )
    else:
        # тут будем если нашли невалидные аккаунты и не смогли найти замену им
        await messages_service.edit_msg.edit(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                "categories",
                "not_enough_products_on_server"
            ),
            event_message_key='successful_purchase',
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
    messages_service: Messages,
    catalog_modul: CatalogModule,
    tg_client: TelegramClient,
):

    category = await check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
        tg_client=tg_client,
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
            discount_sum, promo_code = await catalog_modul.promo_code_service.discount_calculation(
                amount=total_sum, promo_code_id=promo_code_id
            )
            total_sum = max(0, total_sum - discount_sum)

            # если минимальная сумма активации промокода не достигнута
            if promo_code and promo_code.min_order_amount > total_sum:
                await callback.answer(
                    get_text(
                        user.language,
                        "discount",
                        "minimum_amount_to_apply_promo_code"
                    ).format(amount=promo_code.min_order_amount),
                    show_alert=True
                )
                return
        except InvalidPromoCode:
            await callback.answer(
                get_text(
                    user.language,
                    "discount",
                    "promo_code_no_longer_valid_warning"),
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
            user=user,
            messages_service=messages_service,
        )
        return

    message_load = await messages_service.send_msg.send(
        user.user_id, get_text(user.language,"categories","testing_products")
    )
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
            quantity_products=quantity_products,
            messages_service=messages_service,
            catalog_modul=catalog_modul,
        )

    except CategoryNotFound as e:
        await delete_message()
        try:
            await tg_client.delete_message(user.user_id, callback.message.message_id)
        except Exception:
            pass

        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=get_text(user.language, "categories","category_temporarily_unavailable"),
        )
        return
    except NotEnoughMoney as e:
        await delete_message()
        await _show_not_enough_money(
            e.need_money,
            category_id=category_id,
            quantity_products=quantity_products,
            callback=callback,
            user=user,
            messages_service=messages_service,
        )
        return

