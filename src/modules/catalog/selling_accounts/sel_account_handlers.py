import asyncio

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from src.bot_actions.messages import edit_message, send_message
from src.bot_actions.bot_instance import get_bot
from src.exceptions.service_exceptions import InvalidPromoCode, CategoryNotFound, NotEnoughMoney, NotEnoughAccounts
from src.modules.catalog.selling_accounts.keyboard_sell_acc import all_services_account_kb, \
    main_catalog_account_by_service_kb, account_category_kb, back_in_account_category_kb, confirm_buy_acc_kb, \
    replenishment_and_back_in_cat
from src.modules.catalog.selling_accounts.schemas import BuyAccountsData
from src.modules.catalog.selling_accounts.state_sell_acc import BuyAccount
from src.modules.profile.keyboard_profile import in_profile_kb
from src.services.database.discounts.actions import get_valid_promo_code
from src.services.database.discounts.actions.actions_promo import check_activate_promo_code
from src.services.database.discounts.utils.calculation import discount_calculation
from src.services.database.selling_accounts.actions import get_account_service, get_account_categories_by_category_id
from src.services.database.selling_accounts.actions.action_purchase import purchase_accounts
from src.services.database.selling_accounts.models import AccountCategoryFull
from src.services.database.system.actions import get_ui_image
from src.services.database.users.models import Users
from src.utils.converter import safe_int_conversion
from src.utils.i18n import get_text

router = Router()

async def _check_category(category_id: int, old_message_id: int, user_id: int, language: str) -> AccountCategoryFull | None:
    """
    Если есть категория, то вернёт её, если не найдена, то отошлёт соответсвующее сообщение и удалит прошлое
    :return: Если есть категория, то вернёт AccountCategoryFull, иначе None
    """
    category = await get_account_categories_by_category_id(category_id, language=language)
    if not category:
        try:
            bot = await get_bot()
            await bot.delete_message(user_id, old_message_id)
        except Exception:
            pass

        await send_message(
            chat_id=user_id,
            message=get_text(language, 'catalog',"The category is temporarily unavailable"),
        )
        return None

    return category


@router.callback_query(F.data == "show_catalog_services_accounts")
async def show_catalog_services_accounts(callback: CallbackQuery, user: Users):
    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='account_catalog',
        fallback_image_key='default_catalog_account',
        reply_markup=await all_services_account_kb(user.language)
    )


@router.callback_query(F.data.startswith("show_service_acc:"))
async def show_service_acc(callback: CallbackQuery, user: Users):
    service_id = int(callback.data.split(':')[1])
    service = await get_account_service(service_id)

    if not service:
        await callback.message.answer(get_text(user.language, 'catalog',"The services is temporarily unavailable"))

    await edit_message(
        chat_id=callback.from_user.id,
        message_id=callback.message.message_id,
        image_key='account_catalog',
        fallback_image_key='default_catalog_account',
        reply_markup=await main_catalog_account_by_service_kb(user.language, service_id=service_id)
    )


async def edit_message_account_category(
        user: Users,
        message_id: int,
        data: BuyAccountsData,
        category: AccountCategoryFull
):
    ui_image = await get_ui_image(category.ui_image_key)

    message = None
    if category.is_accounts_storage:
        message_discount = ''
        total_price = data.quantity_for_buying * category.price_one_account

        # расчёт скидки
        if data.promo_code:
            if data.promo_code_amount:
                # если скида фиксированное число
                discount = data.promo_code_amount
            else:
                # если скидка в процентах
                discount = (data.quantity_for_buying * category.price_one_account) * data.discount_percentage / 100

            total_price = max(0, total_price - discount)
            message_discount = get_text(user.language, 'catalog',"Discount with promo code: {discount}\n").format(discount=discount)

        service = await get_account_service(category.account_service_id)
        message = get_text(
            user.language,
            'catalog',
            "{name} \n\n"
            "Service: {service_name}\n"
            "Description: {description}\n"
            "Price per account: {price_one_account} ₽ \n\n"
            "Accounts selected: {selected_accounts}\n"
            "{discount}"
            "Total: {total_price}\n\n"
            "To specify the required quantity, send the bot a number"
        ).format(
            name=category.name,
            service_name=service.name if service else 'None',
            description=category.description,
            price_one_account=category.price_one_account,
            selected_accounts=data.quantity_for_buying,
            discount=message_discount,
            total_price=total_price
        )

    await edit_message(
        chat_id=user.user_id,
        message_id=message_id,
        message=message,
        image_key=category.ui_image_key if (ui_image and ui_image.show) else 'default_catalog_account',
        reply_markup=await account_category_kb(
            user.language,
            category=category,
            quantity_for_buying=data.quantity_for_buying,
            promo_code_id=data.promo_code_id
        )
    )

@router.callback_query(F.data.startswith("show_account_category:"))
async def show_account_category(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    quantity_account = int(callback.data.split(':')[2]) # число аккаунтов на приобретение

    category = await _check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    if category.is_accounts_storage:
        # попадём сюда если пользователь произвёл действия на категории, где хранятся аккаунты

        if category.quantity_product_account < quantity_account:  # если имеется меньше, чем хочет пользователь
            await callback.answer(get_text(user.language, 'catalog','No longer in stock'))
            return
        if quantity_account < 0:
            await callback.answer('')  # что бы не весело сообщение
            return

        # обновление данных в состоянии
        data = BuyAccountsData(**(await state.get_data()))
        data.quantity_for_buying = quantity_account
        data.old_message_id = callback.message.message_id
        data.category_id = category_id

        await state.update_data(**data.model_dump())
        await state.set_state(BuyAccount.quantity_accounts)
    else:
        # если пользователь перемещается оп категориям (так же может выйти назад с категории)
        await state.clear()
        data = BuyAccountsData(old_message_id=callback.message.message_id, category_id=category.account_category_id)
        await state.update_data(**data.model_dump())

    await edit_message_account_category(
        user=user,
        message_id=callback.message.message_id,
        data=data,
        category=category
    )


@router.message(BuyAccount.quantity_accounts)
async def set_quantity_accounts(message: Message, state: FSMContext, user: Users):
    try:
        await message.delete()
    except Exception:
        pass # если пользователь удалил сам

    data = BuyAccountsData(**(await state.get_data()))

    category = await _check_category(
        category_id=data.category_id,
        old_message_id=data.old_message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    new_quantity_accounts = safe_int_conversion(value=message.text, default=None, positive=True)
    sent_message = None
    if new_quantity_accounts is None:
        sent_message = await send_message(user.user_id, get_text(user.language, 'catalog',"Incorrect value entered"))
    elif new_quantity_accounts > category.quantity_product_account:
        sent_message = await send_message(user.user_id, get_text(user.language, 'catalog',"No longer in stock"))
    else:
        data.quantity_for_buying = new_quantity_accounts
        await state.update_data(**data.model_dump())

    await state.set_state(BuyAccount.quantity_accounts)

    if sent_message: # удаление старого сообщения о некорректном значении
        await asyncio.sleep(3)
        try:
            await sent_message.delete()
        except Exception:
            pass  # если пользователь удалил сам
        return


    await edit_message_account_category(
        user=user,
        message_id=data.old_message_id,
        data=data,
        category=category
    )



@router.callback_query(F.data.startswith('enter_promo:'))
async def enter_promo(callback: CallbackQuery, state: FSMContext, user: Users):
    category_id = int(callback.data.split(':')[1])
    quantity_account = int(callback.data.split(':')[2]) # число аккаунтов на приобретение

    category = await _check_category(
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
        message=get_text(user.language, 'catalog',"Enter the activation code"),
        image_key='entering_promo_code',
        reply_markup=back_in_account_category_kb(
            user.language,
            category_id=category.account_category_id,
            quantity_for_buying=quantity_account
        )
    )

    await state.set_state(BuyAccount.promo_code)
    await state.update_data(old_message_id=callback.message.message_id)


@router.message(BuyAccount.promo_code)
async def set_promo_code(message: Message, state: FSMContext, user: Users):
    try:
        await message.delete()
    except Exception:
        pass

    promo = await get_valid_promo_code(message.text)
    data = BuyAccountsData(**(await state.get_data()))

    category = await _check_category(
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
        await state.set_state(BuyAccount.promo_code)
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
        await state.set_state(BuyAccount.promo_code)
        return

    await state.update_data(
        promo_code_id = promo.promo_code_id,
        promo_code = promo.activation_code,
        promo_code_amount = promo.amount,
        discount_percentage = promo.discount_percentage,
    )

    await edit_message_account_category(
        user = user,
        message_id = data.old_message_id,
        data = BuyAccountsData(**(await state.get_data())),
        category = category
    )

    promo_message = await send_message(user.user_id, 'The promo code has been successfully activated')
    await asyncio.sleep(3)
    try:
        await promo_message.delete()
    except Exception:
        pass  # если пользователь удалил сам
    return


@router.callback_query(F.data.startswith('confirm_buy_acc:'))
async def confirm_buy_acc(callback: CallbackQuery, user: Users):
    category_id = int(callback.data.split(':')[1])
    quantity_account = int(callback.data.split(':')[2]) # число аккаунтов на приобретение
    promo_code_id = safe_int_conversion(callback.data.split(':')[3], positive=True) # либо int, либо "None"

    if quantity_account <= 0:
        await callback.answer(get_text(user.language, 'catalog',"Select at least one account"))
        return

    category = await _check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    total_sum = category.price_one_account * quantity_account

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
            'catalog',
            "Confirm your purchase\n\n"
            "{category_name}\n"
            "Accounts will be received: {quantity_account}\n"
            "Your balance: {balance}\n"
            "Due: {total_sum}"
        ).format(
            category_name=category.name,
            quantity_account=quantity_account,
            balance=user.balance,
            total_sum=total_sum
        ),
        image_key = 'confirm_purchase',
        fallback_image_key = "default_catalog_account",
        reply_markup=confirm_buy_acc_kb(
            language=user.language,
            category_id=category_id,
            quantity_for_buying=quantity_account,
            promo_code_id=promo_code_id
        )
    )


@router.callback_query(F.data.startswith('buy_acc'))
async def buy_acc(callback: CallbackQuery, user: Users):

    async def _show_not_enough_money(need_money: int):
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(user.language, 'miscellaneous',"Insufficient funds: {amount}").format(amount=need_money),
            image_key='insufficient_funds',
            fallback_image_key="default_catalog_account",
            reply_markup=replenishment_and_back_in_cat(
                language=user.language,
                category_id=category_id,
                quantity_for_buying=quantity_account,
            )
        )

    async def _show_no_enough_accounts():
        await callback.answer(get_text(
                user.language,
                'catalog',
                "There are not enough accounts on the server, please change the number of accounts to purchase"
            ),
            show_alert=True
        )


    category_id = int(callback.data.split(':')[1])
    quantity_account = int(callback.data.split(':')[2])  # число аккаунтов на приобретение
    promo_code_id = safe_int_conversion(callback.data.split(':')[3], positive=True)  # либо int, либо "None"

    category = await _check_category(
        category_id=category_id,
        old_message_id=callback.message.message_id,
        user_id=user.user_id,
        language=user.language
    )
    if category is None:
        return

    # если на сервере недостаточно аккаунтов
    if category.quantity_product_account < quantity_account:
        await _show_no_enough_accounts()
        return

    total_sum = category.price_one_account * quantity_account

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
        await _show_not_enough_money(total_sum - user.balance)
        return

    message_load = await send_message(user.user_id, get_text(user.language,'catalog',"Test accounts..."))
    async def delete_message():
        try:
            await message_load.delete()
        except Exception:
            pass

    result = None
    try:
        result = await purchase_accounts(
            user_id = user.user_id,
            category_id = category_id,
            quantity_accounts = quantity_account,
            promo_code_id = promo_code_id
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
            message=get_text(user.language, 'catalog',"The category is temporarily unavailable"),
        )
        return
    except NotEnoughMoney as e:
        await delete_message()
        await _show_not_enough_money(e.need_money)
        return

    except NotEnoughAccounts as e:
        await delete_message()
        await _show_no_enough_accounts()
        return

    await delete_message()

    # работа с результатом
    if result is True:
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(user.language, 'catalog',"Thank you for your purchase \nThe account is already in the profile"),
            image_key='successful_purchase',
            fallback_image_key="default_catalog_account",
            reply_markup=in_profile_kb(language=user.language)
        )
    else:
        # тут будем если нашли невалидные аккаунты и не смогли найти замену им
        get_text(
            user.language,
            'catalog',
            "There are not enough accounts on the server, please change the number of accounts to purchase"
        ),
        await edit_message(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            message=get_text(
                user.language,
                'catalog',
                "There are not enough accounts on the server, please change the number of accounts to purchase"
            ),
            image_key='successful_purchase',
            fallback_image_key="default_catalog_account",
            reply_markup=back_in_account_category_kb(
                language = user.language,
                category_id=category_id,
                quantity_for_buying=quantity_account,
            )
        )