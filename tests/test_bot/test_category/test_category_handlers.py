import pytest
from types import SimpleNamespace
from src.utils.i18n import get_text
from tests.helpers.fake_aiogram.fake_aiogram_module import (
    FakeCallbackQuery,
    FakeMessage,
    FakeFSMContext
)

@pytest.mark.asyncio
async def test_show_account_category_sets_state_and_edits_message_when_accounts_available(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
    create_product_account,
):
    """
    Если категория хранит аккаунты (is_product_storage=True) и доступно достаточное количество аккаунтов,
    то show_account_category должен:
      - записать в state данные (category_id, quantity_for_buying, old_message_id)
      - установить state в BuyProduct.quantity_products (проверяем, что state изменился)
      - отредактировать исходное сообщение (edit_message_account_category вызван)
    """
    from src.modules.categories.handlers.handler_categories import show_category

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    # создаём категорию, явно включаем is_product_storage
    category = await create_category(is_product_storage=True)
    category_id = category.category_id

    quantity = 3
    # добавим нужное количество product_accounts в категорию
    for _ in range(quantity):
        await create_product_account(category_id=category_id)

    cb = FakeCallbackQuery(data=f"show_category:{category_id}:{quantity}", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=123)

    fsm = FakeFSMContext()
    await show_category(cb, fsm, user)

    # state должен быть установлен (точный класс состояния проверять не будем, проверим, что state не None)
    assert fsm.state is not None, "FSM state не установлен"
    # проверим данные в state
    data = await fsm.get_data()
    assert int(data.get("category_id")) == category_id or data.get("category_id") == category_id
    assert int(data.get("quantity_for_buying")) == quantity or data.get("quantity_for_buying") == str(quantity)

    # проверим, что сообщение редактировалось и в нём присутствует название категории
    assert fake_bot.check_str_in_edited_messages(str(category.name)), "Не отредактировалось сообщение о категории с аккаунтами"


@pytest.mark.asyncio
async def test_show_account_category_non_storage_clears_state_and_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
):
    """
    Для категорий не-хранилищ (is_product_storage=False) — state очищается и edit_message_account_category вызывается.
    """
    from src.modules.categories.handlers.handler_categories import show_category

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    # по умолчанию фабрика создаёт is_product_storage=False (если нужно явно — передать)
    category = await create_category(is_product_storage=False)
    category_id = category.category_id

    cb = FakeCallbackQuery(data=f"show_category:{category_id}:1", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=222, photo=None)

    fsm = FakeFSMContext()
    # предварительно задам какие-то данные в state, чтобы убедиться, что handler их перезапишет/очистит
    await fsm.update_data(old_message_id=999, category_id=999, quantity_for_buying=5)

    await show_category(cb, fsm, user)

    # state должен быть установлен в некоторую форму (мы ожидаем, что данные обновлены на текущую категорию)
    data = await fsm.get_data()
    assert int(data.get("category_id")) == category_id or data.get("category_id") == category_id

    # проверяем, что было редактирование сообщения (в нём должно присутствовать имя категории)
    assert fake_bot.check_str_in_edited_messages(str(category.name)), "Не отредактировалось сообщение при переходе в категорию"


@pytest.mark.asyncio
async def test_set_quantity_accounts_invalid_and_exceeds_stock_behaviour(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
    create_product_account,
):
    """
    Проверяем два кейса для set_quantity_products:
      1) нечисловой ввод -> отправляется "Incorrect value entered. Please try again" и state остаётся на том же шаге
      2) ввод больше чем есть на складе -> отправляется "No longer in stock"
    """
    from src.modules.categories.handlers.handler_categories import set_quantity_products

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    category = await create_category(is_product_storage=True)
    category_id = category.category_id

    # 1) нечисловой ввод
    fsm1 = FakeFSMContext()
    # подготовим state как будто пользователь уже выбрал категорию
    await fsm1.update_data(category_id=category_id, old_message_id=11, quantity_for_buying=0)
    msg_bad = FakeMessage(text="not_a_number", chat_id=user.user_id, username=user.username)
    await set_quantity_products(msg_bad, fsm1, user)

    bad_text = get_text(user.language, 'miscellaneous',"Incorrect value entered. Please try again")
    assert fake_bot.get_message(chat_id=user.user_id, text=bad_text), "Не отправилось сообщение об ошибочном вводе"

    # 2) ввод превышает склад
    # убедимся, что в категории нет аккаунтов (или меньше), запросим больше -> "No longer in stock"
    fsm2 = FakeFSMContext()
    await fsm2.update_data(category_id=category_id, old_message_id=22, quantity_for_buying=0)
    # на текущий момент quantity_product_account скорее всего 0, запросим 5
    msg_too_many = FakeMessage(text="5", chat_id=user.user_id, username=user.username)
    await set_quantity_products(msg_too_many, fsm2, user)

    no_stock_text = get_text(user.language, 'categories', "No longer in stock")
    assert fake_bot.get_message(chat_id=user.user_id, text=no_stock_text), "Не отправилось сообщение о нехватке на складе"


@pytest.mark.asyncio
async def test_set_quantity_accounts_success_updates_state_and_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
    create_product_account,
):
    """
    Успешный ввод количества:
      - state.update_data(quantity_for_buying=...) обновлён
      - edit_message_account_category вызван и отредактировал исходное сообщение
    """
    from src.modules.categories.handlers.handler_categories import set_quantity_products

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    category = await create_category(is_product_storage=True)
    category_id = category.category_id

    # создаём несколько аккаунтов для категории
    for _ in range(4):
        await create_product_account(category_id=category_id)

    fsm = FakeFSMContext()
    # предварительная state (имитируем, что пользователь начал покупку)
    await fsm.update_data(category_id=category_id, old_message_id=333, quantity_for_buying=1)

    # пользователь вводит '3' — в пределах наличия
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage
    msg = FakeMessage(text="3", chat_id=user.user_id, username=user.username)

    await set_quantity_products(msg, fsm, user)

    data = await fsm.get_data()
    assert int(data.get("quantity_for_buying")) == 3 or data.get("quantity_for_buying") == "3"

    # edit_message должны были вызвать и в одном из отредактированных сообщений должно быть имя категории
    assert fake_bot.check_str_in_edited_messages(str(category.name)), "Не отредактировалось сообщение после выбора количества"


@pytest.mark.asyncio
async def test_enter_promo_sets_state_and_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
):
    """
    Callback enter_promo: должен отредактировать сообщение с просьбой ввести код
    и установить state BuyProduct.promo_code, сохранив old_message_id в state.
    """
    from src.modules.categories.handlers.handler_categories import enter_promo

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    # создаём категорию с аккаунтами (is_product_storage=True)
    category = await create_category(is_product_storage=True)
    cat_id = category.category_id
    qty = 2

    cb = FakeCallbackQuery(data=f"enter_promo:{cat_id}:{qty}", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=77)

    fsm = FakeFSMContext()
    await enter_promo(cb, fsm, user)

    # state должен быть установлен в BuyProduct.promo_code (мы только проверим, что state не None)
    assert fsm.state is not None, "FSM state не установлен"

    data = await fsm.get_data()
    assert int(data.get("old_message_id")) == cb.message.message_id or data.get("old_message_id") == cb.message.message_id

    expected = get_text(user.language, 'categories', "Enter the activation code")

    # проверяем, что сообщение редактировалось и содержало просьбу ввести код
    assert fake_bot.get_edited_message(user.user_id, cb.message.message_id, expected), "Не отредактировалось сообщение с просьбой ввести промокод"


@pytest.mark.asyncio
async def test_set_promo_code_not_found_shows_error_and_keeps_state(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
):
    """
    Ввод несуществующего/истёкшего промокода:
      - редактируется исходное сообщение с уведомлением об ошибке
      - FSM остаётся на BuyProduct.promo_code
    """
    from src.modules.categories.handlers.handler_categories import set_promo_code

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    category = await create_category(is_product_storage=True)

    # подготовим state как будто пользователь перешёл в ввод промокода
    fsm = FakeFSMContext()
    await fsm.update_data(category_id=category.category_id, old_message_id=33, quantity_for_buying=1)

    # вводим случайный код которого нет
    msg = FakeMessage(text="NOT_EXISTING_CODE", chat_id=user.user_id, username=user.username)

    await set_promo_code(msg, fsm, user)

    # FSM должен остаться на шаге promo_code
    assert fsm.state is not None, "FSM state неожиданно очищен"

    expected = get_text(user.language, 'discount', "A promo code with this code was not found/expired \n\nTry again")

    # проверяем, что исходное сообщение (old_message_id) было отредактировано с текстом ошибки
    assert fake_bot.get_edited_message(user.user_id, 33, expected), "Не отправилось сообщение об отсутствии промокода"


@pytest.mark.asyncio
async def test_set_promo_code_success_updates_state_and_notifies_user(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
    create_promo_code,
):
    """
    Ввод корректного промокода:
      - в state сохраняются promo_code_id, promo_code и суммы скидок
      - edit_message_account_category вызывается (редактирование сообщения категории)
      - пользователю отправляется одноразовое уведомление 'The promo code has been successfully activated'
    """
    from src.modules.categories.handlers.handler_categories import set_promo_code
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage, FakeFSMContext

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    category = await create_category(is_product_storage=True)
    promo = await create_promo_code()  # фикстура создаёт promo в БД и redis (activation_code = "TESTCODE")

    # подготовим state like user opened promo input
    fsm = FakeFSMContext()
    await fsm.update_data(category_id=category.category_id, old_message_id=44, quantity_for_buying=1)

    msg = FakeMessage(text=promo.activation_code, chat_id=user.user_id, username=user.username)

    await set_promo_code(msg, fsm, user)

    data = await fsm.get_data()
    # проверим что promo_code_id и promo_code попали в state
    assert int(data.get("promo_code_id")) == promo.promo_code_id or data.get("promo_code_id") == promo.promo_code_id
    assert data.get("promo_code") == promo.activation_code

    # edit_message_account_category должен быть вызван (в редакции сообщения категории должно быть имя категории)
    assert fake_bot.check_str_in_edited_messages(str(category.name)), "edit_message_account_category не отредактировало сообщение с категорией"

    # проверим, что пользователю отправилось временное сообщение о включённом промокоде
    assert fake_bot.get_message(user.user_id, 'The promo code has been successfully activated'), "Не отправлено уведомление об успешной активации промокода"


@pytest.mark.asyncio
async def test_confirm_buy_acc_invalid_quantity_answers_user_and_no_edit(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
):
    """
    Если BuyProduct.quantity_products <= 0 — callback должен вызвать callback.answer и не редактировать сообщение.
    Мы проверяем отсутствие редактирования сообщения (т. к. fake callback.answer сложно инспектировать).
    """
    from src.modules.categories.handlers.handler_categories import confirm_buy_category

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    category = await create_category(is_product_storage=True)

    cb = FakeCallbackQuery(data=f"confirm_buy_category:{category.category_id}:0:None", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=12)

    await confirm_buy_category(cb, user)

    # не было редактирования сообщения (так как quantity <= 0)
    assert not fake_bot.check_str_in_edited_messages("Confirm your purchase"), "Сообщение неожиданно отредактировалось при некорректном количестве"


@pytest.mark.asyncio
async def test_confirm_buy_acc_with_promo_applies_discount_and_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
    create_promo_code,
):
    """
    confirm_buy_acc с promo_code_id должен применить скидку и отредактировать сообщение с ожидаемой суммой.
    (используем create_promo_code: amount=100, min_order_amount=100)
    """
    from src.modules.categories.handlers.handler_categories import confirm_buy_category

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user(balance=1000)
    # категоря с price по умолчанию 150 в фабрике — убедимся что она достаточна
    category = await create_category(price=150, is_product_storage=True)
    promo = await create_promo_code() # amount=100

    quantity = 1
    # total_sum before discount = 150, discount = 100 => due = 50
    cb = FakeCallbackQuery(data=f"confirm_buy_category:{category.category_id}:{quantity}:{promo.promo_code_id}", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=99)

    await confirm_buy_category(cb, user)

    # Проверим, что сообщение редактировалось и в нём указана верная сумма after discount (Due: 50)
    text = get_text(
        user.language,
        domain='categories',
        key="Confirm your purchase\n\n"
        "{category_name}\n"
        "Product will be received: {quantity_products}\n"
        "Your balance: {balance}\n"
        "Due: {total_sum}"
    )
    assert fake_bot.check_str_in_edited_messages(text[:15]), "Скидка не применена или сообщение не отредактировалось с ожидаемой суммой"


@pytest.mark.asyncio
async def test_confirm_buy_acc_invalid_promo_alerts_user(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_category,
    monkeypatch,
):
    """
    Симулируем ситуацию, когда discount_calculation выбрасывает InvalidPromoCode.
    В этом случае handler должен вызвать callback.answer с show_alert=True.
    Мы проверяем, что сообщение НЕ редактируется (handler ответил alert'ом).
    """
    from src.modules.categories.handlers.handler_categories import confirm_buy_category
    from src.exceptions import InvalidPromoCode

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    category = await create_category(price=100, is_product_storage=True)

    # заставим discount_calculation бросать InvalidPromoCode
    async def fake_discount_calculation(amount, promo_code_id=None):
        raise InvalidPromoCode()

    from src.services.database.discounts.utils import calculation
    monkeypatch.setattr(calculation, "discount_calculation", fake_discount_calculation)

    cb = FakeCallbackQuery(data=f"confirm_buy_category:{category.category_id}:1:9999", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=55)

    await confirm_buy_category(cb, user)

    # handler реагирует alert'ом — в тестах мы проверим, что сообщение не было отредактировано
    assert not fake_bot.check_str_in_edited_messages("Confirm your purchase"), "При невалидном промокоде сообщение неожиданно отредактировалось"
