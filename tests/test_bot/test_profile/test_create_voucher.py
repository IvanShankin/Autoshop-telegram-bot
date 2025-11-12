import pytest
from types import SimpleNamespace

from src.utils.i18n import get_text
from tests.helpers.fake_aiogram.fake_aiogram_module import FakeFSMContext

@pytest.mark.asyncio
async def test_create_voucher_start_callback(
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
):
    """
    При callback 'create_voucher' — бот очищает state, редактирует сообщение с просьбой ввести сумму.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery

    fake_bot = replacement_fake_bot
    user = await create_new_user()

    fake_cb = FakeCallbackQuery(data="create_voucher", chat_id=user.user_id, username=user.username)
    fake_cb.message = SimpleNamespace(message_id=11)

    fsm = FakeFSMContext()
    await module.create_voucher(fake_cb, fsm, user)

    text = get_text(user.language, 'profile_messages', 'Enter the amount')

    # проверяем, что бот отредактировал сообщение
    assert fake_bot.get_edited_message(user.user_id, 11, text), "Не отправился запрос на ввод суммы"


@pytest.mark.asyncio
async def test_create_voucher_invalid_amount(
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
):
    """
    Невалидное значение суммы (например, строка) — бот сообщает об ошибке и не меняет state.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage

    fake_bot = replacement_fake_bot
    user = await create_new_user()

    msg = FakeMessage(text="not_number", chat_id=user.user_id, username=user.username)
    fsm = FakeFSMContext()

    await module.create_voucher_get_amount(msg, fsm, user)

    text = get_text(user.language, 'miscellaneous', 'Incorrect value entered')

    assert fake_bot.get_message(user.user_id, text), "Не отправилось сообщение об ошибке"


@pytest.mark.asyncio
async def test_create_voucher_valid_amount_prompts_for_activations(
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
):
    """
    Корректная сумма — сохраняется в FSM, бот просит ввести число активаций.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage

    fake_bot = replacement_fake_bot
    user = await create_new_user()

    msg = FakeMessage(text="100", chat_id=user.user_id, username=user.username)
    fsm = FakeFSMContext()

    await module.create_voucher_get_amount(msg, fsm, user)

    assert fsm.data.get("amount") == "100", "FSM не сохранил сумму"
    text = get_text(user.language, 'profile_messages', 'Enter the number of activations for the voucher')
    assert fake_bot.get_message(user.user_id, text), "Не отправилось сообщение о вводе числа активаций"


@pytest.mark.asyncio
async def test_create_voucher_not_enough_money(
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
):
    """
    Пользователь вводит корректное число активаций, но не хватает средств — бот сообщает об этом.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage

    fake_bot = replacement_fake_bot
    user = await create_new_user(balance=10)

    fsm = FakeFSMContext()
    await fsm.update_data(amount=100)

    msg = FakeMessage(text="2", chat_id=user.user_id, username=user.username)
    await module.create_voucher_get_number_of_activations(msg, fsm, user)

    text = get_text(user.language, 'miscellaneous', 'Insufficient funds: {amount}').format(amount=190)
    assert fake_bot.get_message(user.user_id, text), "Не отправилось сообщение о нехватке средств"


@pytest.mark.asyncio
async def test_confirm_create_voucher_not_enough_money_exception(
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
):
    """
    confirm_create_voucher — при NotEnoughMoney редактируется сообщение с текстом об ошибке.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery

    fake_bot = replacement_fake_bot
    user = await create_new_user(balance=0)

    fsm = FakeFSMContext()
    await fsm.update_data(amount=100, number_of_activations=5)

    cb = FakeCallbackQuery(data="confirm_create_voucher", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=101)

    await module.confirm_create_voucher(cb, fsm, user)

    text_1 = get_text(user.language, 'miscellaneous', 'The funds have not been written off')
    text_2 = get_text(user.language, 'miscellaneous', 'Insufficient funds: {amount}').format(amount=500)
    text = f"{text_1}\n\n{text_2}"

    assert fake_bot.get_edited_message(user.user_id, 101, text), "Не отправилось сообщение об ошибке при недостатке средств"


@pytest.mark.asyncio
async def test_confirm_create_voucher_success(
    patch_fake_aiogram,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
):
    """
    Успешное создание ваучера — бот отправляет сообщение об успешном создании.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery
    from src.services.database.discounts.actions import get_valid_voucher_by_user_page

    fake_bot = replacement_fake_bot
    bot_me = await fake_bot.me()
    user = await create_new_user(balance=1000)

    fsm = FakeFSMContext()
    await fsm.update_data(amount=100, number_of_activations=2)

    cb = FakeCallbackQuery(data="confirm_create_voucher", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=55)

    await module.confirm_create_voucher(cb, fsm, user)

    vouchers = await get_valid_voucher_by_user_page(user.user_id)

    text = get_text(user.language, 'profile_messages',
        "Voucher successfully created. \n\nActivation link: <a href='{link}'>Ссылка</a> \nAmount: {amount} \n"
        "Number of activations: {number_activations} \nTotal amount spent on activation: {total_sum} \n"
        "Current balance: {balance} \n\nNote: One user can only activate one voucher"
    ).format(
        link=f'https://t.me/{bot_me.username}?start=voucher_{vouchers[0].activation_code}',
        amount=100,
        number_activations=2,
        total_sum=200,
        balance=user.balance - 200
    )
    assert fake_bot.get_edited_message(user.user_id, cb.message.message_id, text), "Не отправилось сообщение об успешном создании ваучера"
