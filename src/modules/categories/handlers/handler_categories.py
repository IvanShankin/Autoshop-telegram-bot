import asyncio

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.application.bot import Messages
from src.application.models.modules import CatalogModule
from src.database.models.users import Users
from src.exceptions import InvalidPromoCode
from src.infrastructure.telegram.bot_client import TelegramClient
from src.infrastructure.telegram.ui.keyboard import support_kb
from src.middlewares.aiogram_middleware import I18nKeyFilter
from src.modules.categories.keyboards import subscription_prompt_kb, confirm_buy_kb, main_categories_kb
from src.modules.categories.services import check_category, edit_message_category, buy_product
from src.modules.categories.shemas import BuyProductsData
from src.modules.categories.states import BuyProduct
from src.utils.converter import safe_int_conversion
from src.infrastructure.translations import get_text

router_with_repl_kb = Router()
router = Router()


@router_with_repl_kb.message(I18nKeyFilter("product_categories"))
async def handle_catalog_message(
    message: Message,
    state: FSMContext,
    user: Users,
    messages_service: Messages,
    catalog_modul: CatalogModule,
    tg_client: TelegramClient,
):
    await state.clear()

    if await catalog_modul.subscription_service.get(user.user_id): # если пользователю ранее не предлагали подписаться
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=get_text(
                user.language,
                "categories",
                "subscribe_to_channel_prompt"
            ),
            event_message_key='subscription_prompt',
            reply_markup=await subscription_prompt_kb(user.language, catalog_modul, tg_client=tg_client)
        )
        return

    await message_in_main_category(user, messages_service, catalog_modul)


async def message_in_main_category(
    user: Users, messages_service: Messages, catalog_modul: CatalogModule, old_message_id: int | None = None,
):
    """
    :param user: пользователь
    :param old_message_id: если указать, то сообщение с данным id будет отредактировано, иначе отправится новое
    """

    if not await catalog_modul.category_service.get_categories(language=user.language):
        settings = await catalog_modul.settings_service.get_settings()
        await messages_service.send_msg.send(
            chat_id=user.user_id,
            message=get_text(user.language, "categories", "no_categories_available"),
            reply_markup=await support_kb(user.language, support_username=settings.support_username)
        )
        return

    if old_message_id:
        await messages_service.edit_msg.edit(
            message_id=old_message_id,
            chat_id=user.user_id,
            event_message_key='main_category',
            fallback_image_key="default_catalog_account",
            reply_markup=await main_categories_kb(user.language, catalog_modul)
        )
        return

    await messages_service.send_msg.send(
        chat_id=user.user_id,
        event_message_key='main_category',
        fallback_image_key="default_catalog_account",
        reply_markup=await main_categories_kb(user.language, catalog_modul)
    )


@router.callback_query(F.data == "skip_subscription")
async def skip_subscription(
    callback: CallbackQuery, state: FSMContext, user: Users, messages_service: Messages, catalog_modul: CatalogModule
):
    await state.clear()
    await catalog_modul.subscription_service.delete(callback.from_user.id) # больше не просим подписаться

    await message_in_main_category(
        user=user,
        old_message_id=callback.message.message_id,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )


@router.callback_query(F.data == "show_main_categories")
async def show_main_categories(
    callback: CallbackQuery, state: FSMContext, user: Users, messages_service: Messages, catalog_modul: CatalogModule
):
    await state.clear()
    await message_in_main_category(
        user=user,
        old_message_id=callback.message.message_id,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )


@router.callback_query(F.data.startswith("show_category:"))
async def show_category(
    callback: CallbackQuery, state: FSMContext, user: Users, messages_service: Messages, catalog_modul: CatalogModule
):
    category_id = int(callback.data.split(':')[1])
    quantity_products = int(callback.data.split(':')[2]) # число аккаунтов на приобретение

    category = await check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )
    if category is None:
        return

    if category.is_product_storage:
        # попадём сюда если пользователь произвёл действия на категории, где хранятся аккаунты

        # если имеется меньше, чем хочет пользователь и у категории нельзя переиспользовать продукт
        if category.quantity_product < quantity_products and not category.reuse_product:
            await callback.answer(get_text(user.language, "categories",'out_of_stock'))
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
        category=category,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )


@router.message(BuyProduct.quantity_products)
async def set_quantity_products(
    message: Message, state: FSMContext, user: Users, messages_service: Messages, catalog_modul: CatalogModule
):
    try:
        await message.delete()
    except Exception:
        pass # если пользователь удалил сам

    data = BuyProductsData(**(await state.get_data()))

    category = await check_category(
        category_id=data.category_id,
        old_message_id=data.old_message_id,
        user_id=user.user_id,
        language=user.language,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )
    if category is None:
        return

    new_quantity_products = safe_int_conversion(value=message.text, default=None, positive=True)
    sent_message = None
    if new_quantity_products is None:
        sent_message = await messages_service.send_msg.send(
            user.user_id, get_text(user.language, "miscellaneous","incorrect_value_entered")
        )
    elif new_quantity_products > category.quantity_product and not category.reuse_product:
        sent_message = await messages_service.send_msg.send(
            user.user_id, get_text(user.language, "categories","out_of_stock")
        )
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
        category=category,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )


@router.callback_query(F.data.startswith('confirm_buy_category:'))
async def confirm_buy_category(
    callback: CallbackQuery, user: Users, messages_service: Messages, catalog_modul: CatalogModule
):
    category_id = int(callback.data.split(':')[1])
    quantity_products = int(callback.data.split(':')[2]) # число аккаунтов на приобретение
    promo_code_id = safe_int_conversion(callback.data.split(':')[3], positive=True) # либо int, либо "None"

    if quantity_products <= 0:
        await callback.answer(get_text(user.language, "categories","select_at_least_one_product"))
        return

    category = await check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )
    if category is None:
        return

    total_sum = category.price * quantity_products

    if promo_code_id is not None: # если есть promo_code_id
        try:
            discount_sum, _ = await catalog_modul.promo_code_service.discount_calculation(
                amount=total_sum, promo_code_id=promo_code_id
            )
            total_sum = max(0, total_sum - discount_sum)
        except InvalidPromoCode:
            await callback.answer(
                get_text(
                    user.language,
                    "discount",
                    "promo_code_no_longer_valid_warning"
                ),
                show_alert=True
            )
            return

    await messages_service.edit_msg.edit(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        message=get_text(
            user.language,
            "categories",
            "purchase_confirmation"
        ).format(
            category_name=category.name,
            quantity_products=quantity_products,
            balance=user.balance,
            total_sum=total_sum
        ),
        event_message_key = 'confirm_purchase',
        fallback_image_key = "default_catalog_account",
        reply_markup=confirm_buy_kb(
            language=user.language,
            category_id=category_id,
            quantity_for_buying=quantity_products,
            promo_code_id=promo_code_id
        )
    )


@router.callback_query(F.data.startswith('buy_in_category:'))
async def buy_in_category(
    callback: CallbackQuery, state: FSMContext, user: Users, messages_service: Messages, catalog_modul: CatalogModule
):
    category_id = int(callback.data.split(':')[1])
    quantity_products = int(callback.data.split(':')[2])  # число продуктов на приобретение
    promo_code_id = safe_int_conversion(callback.data.split(':')[3], positive=True)  # либо int, либо "None"

    await buy_product(
        category_id=category_id,
        promo_code_id=promo_code_id,
        quantity_products=quantity_products,
        callback=callback,
        user=user,
        messages_service=messages_service,
        catalog_modul=catalog_modul,
    )
    await state.clear()