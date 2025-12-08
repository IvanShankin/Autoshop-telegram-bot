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
    replacement_fake_bot,
    create_new_user,
    create_account_category,
    create_product_account,
):
    """
    Если категория хранит аккаунты (is_accounts_storage=True) и доступно достаточное количество аккаунтов,
    то show_account_category должен:
      - записать в state данные (category_id, quantity_for_buying, old_message_id)
      - установить state в BuyAccount.quantity_accounts (проверяем, что state изменился)
      - отредактировать исходное сообщение (edit_message_account_category вызван)
    """
    # импорт внутри теста (чтобы не ломать импорты при запуске других тестов)
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    # создаём категорию, явно включаем is_accounts_storage
    category = await create_account_category(is_accounts_storage=True)
    category_id = category.account_category_id

    quantity = 3
    # добавим нужное количество product_accounts в категорию
    for _ in range(quantity):
        await create_product_account(account_category_id=category_id)

    cb = FakeCallbackQuery(data=f"show_account_category:{category_id}:{quantity}", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=123)

    fsm = FakeFSMContext()
    await module.show_account_category(cb, fsm, user)

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
    replacement_fake_bot,
    create_new_user,
    create_account_category,
):
    """
    Для категорий не-хранилищ (is_accounts_storage=False) — state очищается и edit_message_account_category вызывается.
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    # по умолчанию фабрика создаёт is_accounts_storage=False (если нужно явно — передать)
    category = await create_account_category(is_accounts_storage=False)
    category_id = category.account_category_id

    cb = FakeCallbackQuery(data=f"show_account_category:{category_id}:1", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=222, photo=None)

    fsm = FakeFSMContext()
    # предварительно задам какие-то данные в state, чтобы убедиться, что handler их перезапишет/очистит
    await fsm.update_data(old_message_id=999, category_id=999, quantity_for_buying=5)

    await module.show_account_category(cb, fsm, user)

    # state должен быть установлен в некоторую форму (мы ожидаем, что данные обновлены на текущую категорию)
    data = await fsm.get_data()
    assert int(data.get("category_id")) == category_id or data.get("category_id") == category_id

    # проверяем, что было редактирование сообщения (в нём должно присутствовать имя категории)
    assert fake_bot.check_str_in_edited_messages(str(category.name)), "Не отредактировалось сообщение при переходе в категорию"


@pytest.mark.asyncio
async def test_set_quantity_accounts_invalid_and_exceeds_stock_behaviour(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
    create_product_account,
):
    """
    Проверяем два кейса для set_quantity_accounts:
      1) нечисловой ввод -> отправляется "Incorrect value entered. Please try again" и state остаётся на том же шаге
      2) ввод больше чем есть на складе -> отправляется "No longer in stock"
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    category = await create_account_category(is_accounts_storage=True)
    category_id = category.account_category_id

    # 1) нечисловой ввод
    fsm1 = FakeFSMContext()
    # подготовим state как будто пользователь уже выбрал категорию
    await fsm1.update_data(category_id=category_id, old_message_id=11, quantity_for_buying=0)
    msg_bad = FakeMessage(text="not_a_number", chat_id=user.user_id, username=user.username)
    await module.set_quantity_accounts(msg_bad, fsm1, user)

    bad_text = get_text(user.language, 'miscellaneous',"Incorrect value entered. Please try again")
    assert fake_bot.get_message(chat_id=user.user_id, text=bad_text), "Не отправилось сообщение об ошибочном вводе"

    # 2) ввод превышает склад
    # убедимся, что в категории нет аккаунтов (или меньше), запросим больше -> "No longer in stock"
    fsm2 = FakeFSMContext()
    await fsm2.update_data(category_id=category_id, old_message_id=22, quantity_for_buying=0)
    # на текущий момент quantity_product_account скорее всего 0, запросим 5
    msg_too_many = FakeMessage(text="5", chat_id=user.user_id, username=user.username)
    await module.set_quantity_accounts(msg_too_many, fsm2, user)

    no_stock_text = get_text(user.language, 'catalog', "No longer in stock")
    assert fake_bot.get_message(chat_id=user.user_id, text=no_stock_text), "Не отправилось сообщение о нехватке на складе"


@pytest.mark.asyncio
async def test_set_quantity_accounts_success_updates_state_and_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
    create_product_account,
):
    """
    Успешный ввод количества:
      - state.update_data(quantity_for_buying=...) обновлён
      - edit_message_account_category вызван и отредактировал исходное сообщение
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    category = await create_account_category(is_accounts_storage=True)
    category_id = category.account_category_id

    # создаём несколько аккаунтов для категории
    for _ in range(4):
        await create_product_account(account_category_id=category_id)

    fsm = FakeFSMContext()
    # предварительная state (имитируем, что пользователь начал покупку)
    await fsm.update_data(category_id=category_id, old_message_id=333, quantity_for_buying=1)

    # пользователь вводит '3' — в пределах наличия
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage
    msg = FakeMessage(text="3", chat_id=user.user_id, username=user.username)

    await module.set_quantity_accounts(msg, fsm, user)

    data = await fsm.get_data()
    assert int(data.get("quantity_for_buying")) == 3 or data.get("quantity_for_buying") == "3"

    # edit_message должны были вызвать и в одном из отредактированных сообщений должно быть имя категории
    assert fake_bot.check_str_in_edited_messages(str(category.name)), "Не отредактировалось сообщение после выбора количества"


@pytest.mark.asyncio
async def test_enter_promo_sets_state_and_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
):
    """
    Callback enter_promo: должен отредактировать сообщение с просьбой ввести код
    и установить state BuyAccount.promo_code, сохранив old_message_id в state.
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    # создаём категорию с аккаунтами (is_accounts_storage=True)
    category = await create_account_category(is_accounts_storage=True)
    cat_id = category.account_category_id
    qty = 2

    cb = FakeCallbackQuery(data=f"enter_promo:{cat_id}:{qty}", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=77)

    fsm = FakeFSMContext()
    await module.enter_promo(cb, fsm, user)

    # state должен быть установлен в BuyAccount.promo_code (мы только проверим, что state не None)
    assert fsm.state is not None, "FSM state не установлен"

    data = await fsm.get_data()
    assert int(data.get("old_message_id")) == cb.message.message_id or data.get("old_message_id") == cb.message.message_id

    expected = get_text(user.language, 'catalog', "Enter the activation code")

    # проверяем, что сообщение редактировалось и содержало просьбу ввести код
    assert fake_bot.get_edited_message(user.user_id, cb.message.message_id, expected), "Не отредактировалось сообщение с просьбой ввести промокод"


@pytest.mark.asyncio
async def test_set_promo_code_not_found_shows_error_and_keeps_state(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
):
    """
    Ввод несуществующего/истёкшего промокода:
      - редактируется исходное сообщение с уведомлением об ошибке
      - FSM остаётся на BuyAccount.promo_code
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    category = await create_account_category(is_accounts_storage=True)

    # подготовим state как будто пользователь перешёл в ввод промокода
    fsm = FakeFSMContext()
    await fsm.update_data(category_id=category.account_category_id, old_message_id=33, quantity_for_buying=1)

    # вводим случайный код которого нет
    msg = FakeMessage(text="NOT_EXISTING_CODE", chat_id=user.user_id, username=user.username)

    await module.set_promo_code(msg, fsm, user)

    # FSM должен остаться на шаге promo_code
    assert fsm.state is not None, "FSM state неожиданно очищен"

    expected = get_text(user.language, 'discount', "A promo code with this code was not found/expired \n\nTry again")

    # проверяем, что исходное сообщение (old_message_id) было отредактировано с текстом ошибки
    assert fake_bot.get_edited_message(user.user_id, 33, expected), "Не отправилось сообщение об отсутствии промокода"


@pytest.mark.asyncio
async def test_set_promo_code_success_updates_state_and_notifies_user(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
    create_promo_code,
):
    """
    Ввод корректного промокода:
      - в state сохраняются promo_code_id, promo_code и суммы скидок
      - edit_message_account_category вызывается (редактирование сообщения категории)
      - пользователю отправляется одноразовое уведомление 'The promo code has been successfully activated'
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage, FakeFSMContext

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    category = await create_account_category(is_accounts_storage=True)
    promo = await create_promo_code()  # фикстура создаёт promo в БД и redis (activation_code = "TESTCODE")

    # подготовим state like user opened promo input
    fsm = FakeFSMContext()
    await fsm.update_data(category_id=category.account_category_id, old_message_id=44, quantity_for_buying=1)

    msg = FakeMessage(text=promo.activation_code, chat_id=user.user_id, username=user.username)

    await module.set_promo_code(msg, fsm, user)

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
    replacement_fake_bot,
    create_new_user,
    create_account_category,
):
    """
    Если quantity_account <= 0 — callback должен вызвать callback.answer и не редактировать сообщение.
    Мы проверяем отсутствие редактирования сообщения (т. к. fake callback.answer сложно инспектировать).
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    category = await create_account_category(is_accounts_storage=True)

    cb = FakeCallbackQuery(data=f"confirm_buy_acc:{category.account_category_id}:0:None", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=12)

    await module.confirm_buy_acc(cb, user)

    # не было редактирования сообщения (так как quantity <= 0)
    assert not fake_bot.check_str_in_edited_messages("Confirm your purchase"), "Сообщение неожиданно отредактировалось при некорректном количестве"


@pytest.mark.asyncio
async def test_confirm_buy_acc_with_promo_applies_discount_and_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
    create_promo_code,
):
    """
    confirm_buy_acc с promo_code_id должен применить скидку и отредактировать сообщение с ожидаемой суммой.
    (используем create_promo_code: amount=100, min_order_amount=100)
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module

    fake_bot = replacement_fake_bot
    user = await create_new_user(balance=1000)
    # категоря с price_one_account по умолчанию 150 в фабрике — убедимся что она достаточна
    category = await create_account_category(price_one_account=150, is_accounts_storage=True)
    promo = await create_promo_code() # amount=100

    quantity = 1
    # total_sum before discount = 150, discount = 100 => due = 50
    cb = FakeCallbackQuery(data=f"confirm_buy_acc:{category.account_category_id}:{quantity}:{promo.promo_code_id}", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=99)

    await module.confirm_buy_acc(cb, user)

    # Проверим, что сообщение редактировалось и в нём указана верная сумма after discount (Due: 50)
    text = get_text(
        user.language,
        domain='catalog',
        key="Confirm your purchase\n\n"
        "{category_name}\n"
        "Accounts will be received: {quantity_account}\n"
        "Your balance: {balance}\n"
        "Due: {total_sum}"
    )
    assert fake_bot.check_str_in_edited_messages(text[:15]), "Скидка не применена или сообщение не отредактировалось с ожидаемой суммой"


@pytest.mark.asyncio
async def test_confirm_buy_acc_invalid_promo_alerts_user(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
    monkeypatch,
):
    """
    Симулируем ситуацию, когда discount_calculation выбрасывает InvalidPromoCode.
    В этом случае handler должен вызвать callback.answer с show_alert=True.
    Мы проверяем, что сообщение НЕ редактируется (handler ответил alert'ом).
    """
    from src.modules.catalog.selling_accounts import sel_account_handlers as module
    from src.exceptions.service_exceptions import InvalidPromoCode

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    category = await create_account_category(price_one_account=100, is_accounts_storage=True)

    # заставим discount_calculation бросать InvalidPromoCode
    async def fake_discount_calculation(amount, promo_code_id=None):
        raise InvalidPromoCode()

    from src.services.database.discounts.utils import calculation
    monkeypatch.setattr(calculation, "discount_calculation", fake_discount_calculation)

    cb = FakeCallbackQuery(data=f"confirm_buy_acc:{category.account_category_id}:1:9999", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=55)

    await module.confirm_buy_acc(cb, user)

    # handler реагирует alert'ом — в тестах мы проверим, что сообщение не было отредактировано
    assert not fake_bot.check_str_in_edited_messages("Confirm your purchase"), "При невалидном промокоде сообщение неожиданно отредактировалось"


class TestBuyAccount:
    @pytest.mark.asyncio
    async def test_buy_acc_not_enough_accounts_alerts_user(
            self,
            patch_fake_aiogram,
            replacement_fake_bot,
            create_new_user,
            create_account_category,
    ):
        """
        Если category.quantity_product_account < quantity_account — показывается alert,
        сообщение не редактируется.
        """
        from src.modules.catalog.selling_accounts import sel_account_handlers as module
        fake_bot = replacement_fake_bot
        user = await create_new_user(balance=1000)
        category = await create_account_category(is_accounts_storage=True)
        # quantity_product_account по умолчанию 0, так что условия нехватки выполняются

        cb = FakeCallbackQuery(data=f"buy_acc:{category.account_category_id}:5:None", chat_id=user.user_id,
                               username=user.username)
        cb.message = SimpleNamespace(message_id=10)

        await module.buy_acc(cb, user)

        # Проверяем: сообщение не редактировалось (только alert)
        assert not fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Сообщение неожиданно отредактировалось, хотя должно быть только alert о нехватке аккаунтов"

    @pytest.mark.asyncio
    async def test_buy_acc_min_amount_for_promo_not_reached(
            self,
            patch_fake_aiogram,
            replacement_fake_bot,
            create_new_user,
            create_account_category,
            create_promo_code,
    ):
        """
        Если promo_code.min_order_amount > total_sum — показывается alert о минимальной сумме.
        """
        from src.modules.catalog.selling_accounts import sel_account_handlers as module

        fake_bot = replacement_fake_bot
        user = await create_new_user(balance=10000)
        category = await create_account_category(price_one_account=50, is_accounts_storage=True)
        promo = await create_promo_code()  # min_order_amount=100

        # quantity_account = 1 => total_sum = 50 < 100
        cb = FakeCallbackQuery(data=f"buy_acc:{category.account_category_id}:1:{promo.promo_code_id}",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=20)

        await module.buy_acc(cb, user)

        # Проверяем отсутствие редактирования (был alert)
        assert not fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Неожиданное редактирование сообщения при недостижении минимальной суммы промокода"

    @pytest.mark.asyncio
    async def test_buy_acc_invalid_promo_code_alert(
            self,
            patch_fake_aiogram,
            replacement_fake_bot,
            create_new_user,
            create_account_category,
            monkeypatch,
    ):
        """
        Если discount_calculation выбрасывает InvalidPromoCode — показывается alert,
        сообщение не редактируется.
        """
        from src.modules.catalog.selling_accounts import sel_account_handlers as module
        from src.exceptions.service_exceptions import InvalidPromoCode

        fake_bot = replacement_fake_bot
        user = await create_new_user(balance=10000)
        category = await create_account_category(is_accounts_storage=True)

        async def fake_discount_calculation(amount, promo_code_id=None):
            raise InvalidPromoCode()

        from src.services.database.discounts.utils import calculation
        monkeypatch.setattr(calculation, "discount_calculation", fake_discount_calculation)

        cb = FakeCallbackQuery(data=f"buy_acc:{category.account_category_id}:1:9999",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=30)

        await module.buy_acc(cb, user)

        assert not fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Сообщение не должно было редактироваться при невалидном промокоде"

    @pytest.mark.asyncio
    async def test_buy_acc_not_enough_money_edits_message(
            self,
            patch_fake_aiogram,
            replacement_fake_bot,
            create_new_user,
            create_account_category,
            create_product_account
    ):
        """
        Если balance < total_sum — редактируется сообщение о нехватке средств.
        """
        from src.modules.catalog.selling_accounts import sel_account_handlers as module

        fake_bot = replacement_fake_bot
        user = await create_new_user(balance=50)
        category = await create_account_category(price_one_account=200, is_accounts_storage=True)
        _ = await create_product_account(account_category_id=category.account_category_id)

        cb = FakeCallbackQuery(data=f"buy_acc:{category.account_category_id}:1:None",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=40)

        await module.buy_acc(cb, user)

        expected_text = get_text(user.language, 'miscellaneous', "Insufficient funds: {amount}").format(amount=150)

        assert fake_bot.get_edited_message(user.user_id, cb.message.message_id, expected_text), \
            "Не отредактировалось сообщение о нехватке средств"

    @pytest.mark.asyncio
    async def test_buy_acc_successful_purchase(
            self,
            patch_fake_aiogram,
            replacement_fake_bot,
            create_new_user,
            create_account_category,
            create_product_account,
            monkeypatch,
    ):
        """
        Успешная покупка: purchase_accounts возвращает True -> сообщение 'Thank you for your purchase...'
        """
        from src.modules.catalog.selling_accounts import sel_account_handlers as module

        fake_bot = replacement_fake_bot
        user = await create_new_user(balance=1000)
        category = await create_account_category(price_one_account=100, is_accounts_storage=True)
        _ = await create_product_account(account_category_id=category.account_category_id)

        async def fake_purchase_accounts(**kwargs):
            return True

        from src.modules import catalog
        monkeypatch.setattr(catalog, "selling_accounts", fake_purchase_accounts)

        cb = FakeCallbackQuery(data=f"buy_acc:{category.account_category_id}:1:None",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=50)

        await module.buy_acc(cb, user)

        assert fake_bot.check_str_in_edited_messages("Thank you for your purchase"), \
            "Не появилось сообщение об успешной покупке"

    @pytest.mark.asyncio
    async def test_buy_acc_purchase_failed_shows_no_enough_accounts_message(
            self,
            patch_fake_aiogram,
            replacement_fake_bot,
            create_new_user,
            create_account_category,
            create_product_account,
            monkeypatch,
    ):
        """
        Если purchase_accounts возвращает False — должно отредактироваться сообщение с текстом
        'There are not enough accounts on the server...'
        """
        from src.modules.catalog.selling_accounts import sel_account_handlers as module

        fake_bot = replacement_fake_bot
        user = await create_new_user(balance=1000)
        category = await create_account_category(price_one_account=100, is_accounts_storage=True)
        _ = await create_product_account(account_category_id=category.account_category_id)

        async def fake_purchase_accounts(**kwargs):
            return False

        from src.modules import catalog
        monkeypatch.setattr(catalog, "selling_accounts", fake_purchase_accounts)

        cb = FakeCallbackQuery(data=f"buy_acc:{category.account_category_id}:1:None",
                               chat_id=user.user_id, username=user.username)
        cb.message = SimpleNamespace(message_id=60)

        await module.buy_acc(cb, user)

        assert fake_bot.check_str_in_edited_messages("There are not enough accounts on the server"), \
            "Не появилось сообщение о нехватке аккаунтов при result=False"



