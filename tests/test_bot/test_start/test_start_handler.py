from types import SimpleNamespace

import pytest
from sqlalchemy import select

from helpers.fake_aiogram.fake_aiogram_module import FakeMessage, FakeFSMContext, FakeCallbackQuery
from helpers.helper_fixture import create_new_user, create_settings
from src.middlewares.aiogram_middleware import MaintenanceMiddleware
from src.services.database.database import get_db
from src.services.discounts.models import Vouchers
from src.services.referrals.models import Referrals
from src.services.system.actions import get_settings, update_settings
from src.services.users.actions import get_user
from src.utils.i18n import get_i18n

@pytest.mark.asyncio
async def test_start_non_existing_user(patch_fake_aiogram, replacement_fake_bot):
    """Проверяем: при старте не существующий пользователь получает сообщение с просьбой выбрать язык и его добавляют в БД"""
    from src.modules import start_handler as start

    fake_bot = replacement_fake_bot
    msg = FakeMessage(text="/start", chat_id=123, username="User")

    await start.cmd_start(msg, FakeFSMContext())

    user = await get_user(123)
    assert user # должны добавить пользователя

    assert fake_bot.check_str_in_messages("Select language"), "Не отправилось приветственное сообщение"

@pytest.mark.asyncio
async def test_start_existing_user(patch_fake_aiogram, replacement_fake_bot, create_new_user, create_settings):
    """Проверяем: при старте не существующий пользователь получает сообщение с просьбой выбрать язык и его добавляют в БД"""
    from src.modules import start_handler as start

    fake_bot = replacement_fake_bot

    user = await create_new_user()
    setting = create_settings
    msg = FakeMessage(text="/start", chat_id=user.user_id, username=user.username)

    await start.cmd_start(msg, FakeFSMContext())

    i18n = get_i18n(user.language, 'start_message')
    text = i18n.gettext(
        'Welcome to {shop_name} SHOP! \nOur news channel: @{channel_name} \nHappy shopping!'
    ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)

    assert fake_bot.get_message(user.user_id, text), "Не отправилось приветственное сообщение"

@pytest.mark.asyncio
async def test_start_with_new_referral(patch_fake_aiogram, replacement_fake_bot, create_new_user):
    from src.modules import start_handler as start

    fake_bot = replacement_fake_bot
    owner = await create_new_user()
    msg = FakeMessage(text=f"/start ref:{owner.unique_referral_code}", chat_id=123, username="User")

    await start.cmd_start(msg, FakeFSMContext())

    user = await get_user(123)
    assert user  # должны добавить пользователя
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Referrals)
            .where(
                (Referrals.referral_id == user.user_id) &
                (Referrals.owner_user_id == owner.user_id)
            )
        )
        assert result_db.scalar_one_or_none() # должна появиться запись о новом рефералле


    # сообщение для владельца рефералла
    i18n = get_i18n(owner.language, 'start_message')
    message = i18n.gettext('You have a new referral!')
    assert fake_bot.get_message(owner.user_id, message), "Не отправилось сообщение о новом рефералле"

    # сообщение для того кто запустил бота
    assert fake_bot.check_str_in_messages("Select language"), "Не отправилось приветственное сообщение"

@pytest.mark.asyncio
async def test_start_activate_voucher_existing_user(
        patch_fake_aiogram,
        replacement_fake_bot,
        create_new_user,
        create_voucher
):
    """Активация ваучера уже имеющимся пользователем"""
    from src.modules import start_handler as start
    voucher = await create_voucher()

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    msg = FakeMessage(text=f"/start voucher:{voucher.activation_code}", chat_id=user.user_id, username=user.username)

    await start.cmd_start(msg, FakeFSMContext())

    user = await get_user(user.user_id) # для обновления баланса
    assert user.balance == voucher.amount # т.к. у пользователя не было денег

    i18n = get_i18n(user.language, 'discount_dom')
    text = i18n.gettext(
        "Voucher successfully activated! \n\nVoucher amount: {amount} \nCurrent balance: {new_balance}"
    ).format(amount=voucher.amount, new_balance=user.balance)

    # сообщение для того кто запустил бота
    assert fake_bot.get_message(user.user_id, text), "Не отправилось сообщение об активации ваучера"


@pytest.mark.asyncio
async def test_start_activate_voucher_existing_user(
        patch_fake_aiogram,
        replacement_fake_bot,
        create_new_user,
        create_voucher
):
    """Активация ваучера уже имеющимся пользователем"""
    from src.modules import start_handler as start
    voucher = await create_voucher()
    owner = await get_user(voucher.creator_id)

    fake_bot = replacement_fake_bot
    msg = FakeMessage(text=f"/start voucher:{voucher.activation_code}", chat_id=123, username="user")

    await start.cmd_start(msg, FakeFSMContext())

    user = await get_user(123)
    assert user  # должны добавить пользователя
    assert user.balance == voucher.amount # т.к. у пользователя не было денег

    # должен создаться реферал
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Referrals)
            .where(
                (Referrals.referral_id == user.user_id) &
                (Referrals.owner_user_id == owner.user_id)
            )
        )
        assert result_db.scalar_one_or_none()  # должна появиться запись о новом рефералле

    i18n = get_i18n(user.language, 'discount_dom')
    text = i18n.gettext(
        "Voucher successfully activated! \n\nVoucher amount: {amount} \nCurrent balance: {new_balance}"
    ).format(amount=voucher.amount, new_balance=user.balance)

    # сообщение для того кто запустил бота
    assert fake_bot.get_message(user.user_id, text), "Не отправилось сообщение об активации ваучера"
    assert fake_bot.get_message(user.user_id, "Выберите язык \n\nSelect language"), "Не отправилось сообщение о выборе языка"


async def test_select_language(patch_fake_aiogram, replacement_fake_bot, create_new_user):
    from src.modules import start_handler as start
    user = await create_new_user()
    setting = await get_settings()
    fake_bot = replacement_fake_bot

    callback = FakeCallbackQuery(data = "set_language_after_start:en", chat_id = user.user_id)

    await start.select_language(callback)

    user = await get_user(user.user_id)
    assert user.language == 'en'

    i18n = get_i18n(user.language, 'start_message')
    text = i18n.gettext(
        'Welcome to {shop_name} SHOP! \nOur news channel: @{channel_name} \nHappy shopping!'
    ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)

    assert fake_bot.get_message(user.user_id, text), "Не отправилось приветственное сообщение"


@pytest.mark.asyncio
async def test_maintenance_blocks_normal_user(patch_fake_aiogram, replacement_fake_bot, create_new_user):
    user = await create_new_user()

    setting = await get_settings()
    setting.maintenance_mode = True
    await update_settings(setting)

    bot = replacement_fake_bot
    msg = FakeMessage(chat_id=user.user_id, username="user")

    # middleware
    mw = MaintenanceMiddleware(allow_admins=True)

    # эмулируем хэндлер
    called = {"handler": False}

    async def handler(event, data):
        called["handler"] = True

    await mw(handler, msg, {})

    # проверяем: handler не вызван, бот отправил сообщение
    assert not called["handler"]
    assert "temporarily unavailable" in msg._last_answer[0]

