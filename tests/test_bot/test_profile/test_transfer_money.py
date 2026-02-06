import pytest
from types import SimpleNamespace

from tests.helpers.fake_aiogram.fake_aiogram_module import FakeFSMContext
from src.utils.i18n import get_text


@pytest.mark.asyncio
async def test_transfer_amount_invalid_input(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
):
    """
    Некорректный ввод суммы (нечисло) — отправляется сообщение об ошибке,
    FSM остаётся на том же шаге (мы проверяем отправку сообщения).
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage
    fake_bot = replacement_fake_bot_fix

    # подготовим пользователя и мок get_user
    user = await create_new_user()

    # Подготовим сообщение — нечисловая строка
    fake_msg = FakeMessage(text="not_a_number", chat_id=user.user_id, username=user.username)

    # Используем реальный handler (имя из твоего файла)
    # предполагаю имя функции `transfer_money_get_amount`
    await module.transfer_money_get_amount(fake_msg, FakeFSMContext(), user)

    text = get_text(user.language, "miscellaneous", "incorrect_value_entered")
    assert fake_bot.get_message(chat_id=user.user_id, text=text)


@pytest.mark.asyncio
async def test_transfer_amount_insufficient_funds(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
):
    """
    Ввод суммы, превышающей баланс — отправляется сообщение об отсутствии средств.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot_fix
    # пользователь с балансом 10
    user = await create_new_user(balance=10)

    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage
    fake_msg = FakeMessage(text="1000", chat_id=user.user_id, username=user.username)

    await module.transfer_money_get_amount(fake_msg, FakeFSMContext(), user)

    text = get_text(user.language, "miscellaneous", 'insufficient_funds').format(amount=990)
    assert fake_bot.get_message(chat_id=user.user_id, text=text)


@pytest.mark.asyncio
async def test_transfer_amount_success_sets_state_and_prompts_recipient(
    replacement_needed_modules,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
):
    """
    Корректная сумма — state.update_data(amount=...) и переход в TransferMoney.recipient_id,
    отправляется приглашение ввести ID получателя.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user(balance=1000)

    # подготовим FSM spy
    fsm = FakeFSMContext()

    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage
    fake_msg = FakeMessage(text="500", chat_id=user.user_id, username=user.username)

    await module.transfer_money_get_amount(fake_msg, fsm, user)

    # проверяем, что update_data сохранил amount
    assert fsm.data.get("amount") == "500" or fsm.data.get("amount") == 500, "amount не записался в state"
    # проверяем, что state сменился на recipient (по коду ожидалось TransferMoney.recipient_id)
    assert fsm.state is not None, "Не установлен state после корректной суммы"
    # проверяем, что отправилось приглашение ввести ID

    text = get_text(user.language, "profile_messages", "enter_recipient_id")
    assert fake_bot.get_message(chat_id=user.user_id, text=text)


@pytest.mark.asyncio
async def test_transfer_recipient_not_found(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
):
    """
    Некорректный recipient_id (нет такого пользователя) — отправляется сообщение 'user_not_found'
    """
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user(balance=100)

    # get_user для текущего пользователя возвращаем user,
    # но когда вызывают get_user(int(message.text)) — вернём None
    async def fake_get_user(arg_id, username=None):
        # if called for existing user -> return
        if arg_id == user.user_id:
            return user
        return None
    from src.services.database.users import actions as moduls
    monkeypatch.setattr(moduls, "get_user", fake_get_user)


    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage
    # сначала пользователь вводит amount корректно -> нам нужно симулировать уже обновлённый state
    # но проще — вызвать transfer_money_get_recipient_id напрямую
    fake_msg = FakeMessage(text="99999", chat_id=user.user_id, username=user.username)

    # FSM can be anything (we're not using stored data here)
    await module.transfer_money_get_recipient_id(fake_msg, FakeFSMContext(), user)

    text = get_text(user.language, "miscellaneous", "user_not_found")
    assert fake_bot.get_message(chat_id=user.user_id, text=text)


@pytest.mark.asyncio
async def test_confirm_transfer_money_user_not_found_exception(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
):
    """
    Подтверждение перевода — если money_transfer бросает UserNotFound,
    то редактируется сообщение с текстом об ошибке.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from src.exceptions import UserNotFound

    # подготовим пользователя и state (с данными)
    fake_bot = replacement_fake_bot_fix
    user = await create_new_user(balance=1000)

    # подготовим state.get_data() чтобы подтвердить что передаём нужные данные
    class FSMWithData(FakeFSMContext):
        async def get_data(self):
            return {"amount": "50", "recipient_id": 99999}
    fsm = FSMWithData()

    # заставим money_transfer бросить исключение UserNotFound
    async def fake_money_transfer(sender_id, recipient_id, amount):
        raise UserNotFound()
    from src.services.database.users.actions import action_other_with_user as modul
    monkeypatch.setattr(modul,"money_transfer", fake_money_transfer)

    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery
    cb = FakeCallbackQuery(data="confirm_transfer_money", chat_id=user.user_id, username=user.username)
    # Подменяем callback.message.message_id (в редактировании используется callback.message.message_id)
    cb.message = SimpleNamespace(message_id=42)

    await module.confirm_transfer_money(cb, fsm, user)

    text = get_text(user.language, "miscellaneous", "user_not_found")

    _, chat_id, message_id, text_answer, reply_markup = fake_bot.calls[0]
    assert chat_id == user.user_id
    assert message_id == 42
    assert text in text_answer

@pytest.mark.asyncio
async def test_confirm_transfer_money_success(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    monkeypatch,
    create_new_user,
):
    """
    Успешный перевод: money_transfer отработал — проверяем отправку сообщений и уведомление получателю.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery

    fake_bot = replacement_fake_bot_fix
    sender = await create_new_user(balance=1000)
    recipient = await create_new_user(balance=0)

    # Подготовим FSM с данными
    class FSMWithData(FakeFSMContext):
        async def get_data(self):
            return {"amount": "100", "recipient_id": recipient.user_id}
    fsm = FSMWithData()

    cb = FakeCallbackQuery(data="confirm_transfer_money", chat_id=sender.user_id, username=sender.username)
    cb.message = SimpleNamespace(message_id=99)

    await module.confirm_transfer_money(cb, fsm, sender)

    text = get_text(sender.language, "profile_messages", "funds_successfully_transferred")

    _, chat_id, message_id, text_answer, reply_markup = fake_bot.calls[0]
    assert chat_id == sender.user_id
    assert message_id == 99
    assert text == text_answer

    text = get_text(
        sender.language,
        "profile_messages",
        "funds_transferred_to_your_balance"
    ).format(amount=100, balance=recipient.balance + 100)
    assert fake_bot.get_message(recipient.user_id, text)