from types import SimpleNamespace

import pytest

from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery, FakeFSMContext
from src.config import PAYMENT_LIFETIME_SECONDS
from src.utils.i18n import get_text, n_get_text


@pytest.mark.asyncio
async def test_show_type_replenishment(
    replacement_needed_modules,
    create_new_user,
    replacement_fake_bot,
):
    """Callback 'confirm_deactivate_voucher' — активный ваучер вызывает запрос подтверждения."""
    from src.modules.profile.handlers import replenishment_handler as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()

    cb = FakeCallbackQuery(data=f"show_type_replenishment", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=44)

    await module.show_type_replenishment(cb, FakeFSMContext(), user)

    text = get_text(user.language, 'profile_messages', 'Select the desired services for replenishment')
    assert fake_bot.get_edited_message( user_id = user.user_id, message_id = cb.message.message_id, message = text)




@pytest.mark.asyncio
async def test_get_amount_inactive_type_payment(
    replacement_needed_modules,
    replacement_fake_bot,
    create_new_user,
    monkeypatch,
):
    """Callback 'replenishment:<id>:<name>' — неактивный тип оплаты должен вызвать сообщение о неактивности."""
    from src.modules.profile.handlers import replenishment_handler as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()

    cb = FakeCallbackQuery(
        data="replenishment:1:CryptoBot",
        chat_id=user.user_id,
        username=user.username
    )
    cb.message = SimpleNamespace(message_id=7)

    fsm = FakeFSMContext()

    await module.get_amount(cb, fsm, user)

    text = get_text(user.language, 'profile_messages', "This services is temporarily inactive")

    assert fake_bot.get_edited_message(user.user_id, 7, text), "Не отредактировалось сообщение о неактивном способе пополнения"


@pytest.mark.asyncio
async def test_get_amount_active_success(
    replacement_needed_modules,
    replacement_fake_bot,
    create_new_user,
    create_type_payment,
    monkeypatch,
):
    """Callback 'replenishment:<id>:<name>' — активный тип оплаты корректно открывает ввод суммы."""
    from src.modules.profile.handlers import replenishment_handler as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    type_payment = await create_type_payment()

    cb = FakeCallbackQuery(
        data=f"replenishment:{type_payment.type_payment_id}:CryptoBot",
        chat_id=user.user_id,
        username=user.username
    )
    cb.message = SimpleNamespace(message_id=17)
    fsm = FakeFSMContext()

    await module.get_amount(cb, fsm, user)

    expected_text = get_text(user.language, 'profile_messages', '{name_payment}. Enter the top-up amount in rubles').format(name_payment='CryptoBot')

    assert fake_bot.check_str_in_edited_messages(expected_text), "Не появилось сообщение о вводе суммы пополнения"
    assert fsm.data["payment_id"] == 1, "payment_id не записан в FSM"


# TESTS FOR start_replenishment

@pytest.mark.asyncio
async def test_start_replenishment_invalid_number(
    replacement_needed_modules,
    replacement_fake_bot,
    monkeypatch,
    create_new_user
):
    """Неверное число при вводе суммы — остаёмся на том же шаге и отправляем сообщение об ошибке."""
    from src.modules.profile.handlers import replenishment_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage
    from src.modules.profile.state.replenishment import GetAmount

    user = await create_new_user()

    fsm = FakeFSMContext()
    msg = FakeMessage(text="not_number", chat_id=user.user_id, username=user.username)

    await module.start_replenishment(msg, fsm, user)

    # Проверим, что состояние не сменилось
    assert fsm.state == GetAmount.amount.state, "Состояние FSM должно остаться прежним при ошибочном вводе"


@pytest.mark.asyncio
async def test_start_replenishment_crypto_bot_success(
    replacement_needed_modules,
    replacement_fake_bot,
    monkeypatch,
    create_new_user,
    create_type_payment,
):
    """Корректное создание инвойса через CryptoBot."""
    from src.modules.profile.handlers import replenishment_handler as module
    from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    type_payment = await create_type_payment(name_for_admin='crypto_bot')

    async def fake_create_invoice(**kwargs):
        return "https://test-invoice"

    from src.modules.profile.handlers.replenishment_handler import crypto_bot as modul
    monkeypatch.setattr(modul,"create_invoice", fake_create_invoice)

    # FSM с заранее записанным payment_id
    fsm = FakeFSMContext()
    fsm.data = {"payment_id": 1}

    msg = FakeMessage(text="100", chat_id=user.user_id, username=user.username)
    await module.start_replenishment(msg, fsm, user)

    text = n_get_text(
        user.language,
        'profile_messages',
        "{service_name}. Invoice successfully created. You have {minutes} minute to "
        "pay. After the time expires, the invoice will be canceled. \n\n"
        "Amount: {origin_sum}\n"
        "Payable: {total_sum} ₽ ( + commission {percent}%)",
        "{service_name}. Invoice successfully created. You have {minutes} minutes to "
        "pay. After the time expires, the invoice will be canceled. \n\n"
        "Amount: {origin_sum}\n"
        "Payable: {total_sum} ₽ ( + commission {percent}%)",
        PAYMENT_LIFETIME_SECONDS // 60
    ).format(
        service_name=type_payment.name_for_user,
        minutes=PAYMENT_LIFETIME_SECONDS // 60,
        origin_sum=100,
        total_sum=100 * type_payment.commission // 100 if type_payment.commission else 100,
        percent=type_payment.commission
    )

    assert fake_bot.check_str_in_messages(text), "Не отправилось сообщение об успешном создании счёта CryptoBot"