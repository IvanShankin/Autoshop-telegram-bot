import pytest
from sqlalchemy import select

from tests.helpers.fake_aiogram.fake_aiogram_module import FakeMessage, FakeFSMContext, FakeCallbackQuery, FakeCommandObject
from tests.helpers.helper_fixture import create_new_user, create_settings
from src.services.database.core.database import get_db
from src.services.database.referrals.models import Referrals
from src.services.database.system.actions import get_settings, update_settings
from src.utils.i18n import get_text


@pytest.mark.asyncio
async def test_start_non_existing_user(patch_fake_aiogram, replacement_fake_bot_fix):
    """Проверяем: при старте не существующий пользователь получает сообщение с просьбой выбрать язык и его добавляют в БД"""
    from src.modules import start_handler as start
    from src.services.database.users.actions import get_user

    fake_bot = replacement_fake_bot_fix
    msg = FakeMessage(text="/start", chat_id=123, username="User")
    com = FakeCommandObject(command = "start", args = None)

    await start.cmd_start(msg, com, FakeFSMContext())

    user = await get_user(123)
    assert user # должны добавить пользователя

    assert fake_bot.check_str_in_messages("Select language"), "Не отправилось приветственное сообщение"

@pytest.mark.asyncio
async def test_start_existing_user(patch_fake_aiogram, replacement_fake_bot_fix, create_new_user, create_settings):
    """Проверяем: при старте не существующий пользователь получает сообщение с просьбой выбрать язык и его добавляют в БД"""
    from src.modules import start_handler as start

    fake_bot = replacement_fake_bot_fix

    user = await create_new_user()
    setting = create_settings
    msg = FakeMessage(text="/start", chat_id=user.user_id, username=user.username)
    com = FakeCommandObject(command = "start", args = None)

    await start.cmd_start(msg, com, FakeFSMContext())

    text = get_text(
        user.language,
        'start_message',
        'Welcome to {shop_name} SHOP! \nOur news channel: @{channel_name} \nHappy shopping!'
    ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)

    assert fake_bot.get_message(user.user_id, text), "Не отправилось приветственное сообщение"

@pytest.mark.asyncio
async def test_start_with_new_referral(patch_fake_aiogram, replacement_fake_bot_fix, create_new_user):
    from src.modules import start_handler as start
    from src.services.database.users.actions import get_user

    fake_bot = replacement_fake_bot_fix
    owner = await create_new_user()
    msg = FakeMessage(text=f"/start ref_{owner.unique_referral_code}", chat_id=123, username="User")
    com = FakeCommandObject(command = "start", args = f'ref_{owner.unique_referral_code}')

    await start.cmd_start(msg, com, FakeFSMContext())

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
    message = get_text(
        owner.language,
        'referral_messages',
        "You've invited a new referral!\n"
        "Username: {username}\n\n"
        "Thank you for using our services!"
    ).format(username= f'@{user.username}' if user.username else 'None')
    assert fake_bot.get_message(owner.user_id, message), "Не отправилось сообщение о новом рефералле"

    # сообщение для того кто запустил бота
    assert fake_bot.check_str_in_messages("Select language"), "Не отправилось приветственное сообщение"

@pytest.mark.asyncio
async def test_start_activate_voucher_existing_user_1(
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_voucher
):
    """Активация ваучера уже имеющимся пользователем"""
    from src.modules import start_handler as start
    from src.services.database.users.actions import get_user

    voucher = await create_voucher()

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    msg = FakeMessage(text=f"/start voucher_{voucher.activation_code}", chat_id=user.user_id, username=user.username)
    com = FakeCommandObject(command = "start", args = f'voucher_{voucher.activation_code}')

    await start.cmd_start(msg, com,  FakeFSMContext())

    user = await get_user(user.user_id) # для обновления баланса
    assert user.balance == voucher.amount # т.к. у пользователя не было денег

    text = get_text(
        user.language,
        'discount',
        "Voucher successfully activated! \n\nVoucher amount: {amount} \nCurrent balance: {new_balance}"
    ).format(amount=voucher.amount, new_balance=user.balance)

    # сообщение для того кто запустил бота
    assert fake_bot.get_message(user.user_id, text), "Не отправилось сообщение об активации ваучера"


@pytest.mark.asyncio
async def test_start_activate_voucher_existing_user_2(
        patch_fake_aiogram,
        replacement_fake_bot_fix,
        create_new_user,
        create_voucher
):
    """Активация ваучера уже имеющимся пользователем"""
    from src.modules import start_handler as start
    from src.services.database.users.actions import get_user

    voucher = await create_voucher()
    owner = await get_user(voucher.creator_id)

    fake_bot = replacement_fake_bot_fix
    msg = FakeMessage(text=f"/start voucher_{voucher.activation_code}", chat_id=123, username="user")
    com = FakeCommandObject(command = "start", args = f'voucher_{voucher.activation_code}')

    await start.cmd_start(msg, com, FakeFSMContext())

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

    text = get_text(
        user.language,
        'discount',
        "Voucher successfully activated! \n\nVoucher amount: {amount} \nCurrent balance: {new_balance}"
    ).format(amount=voucher.amount, new_balance=user.balance)

    # сообщение для того кто запустил бота
    assert fake_bot.get_message(user.user_id, text), "Не отправилось сообщение об активации ваучера"
    assert fake_bot.get_message(user.user_id, "Выберите язык \n\nSelect language"), "Не отправилось сообщение о выборе языка"


async def test_select_language(patch_fake_aiogram, replacement_fake_bot_fix, create_new_user):
    from src.modules import start_handler as start
    from src.services.database.users.actions import get_user

    user = await create_new_user()
    setting = await get_settings()
    fake_bot = replacement_fake_bot_fix

    callback = FakeCallbackQuery(data = "set_language_after_start:en", chat_id = user.user_id)

    await start.select_language(callback, user)

    user = await get_user(user.user_id)
    assert user.language == 'en'

    text = get_text(
        user.language,
        'start_message',
        'Welcome to {shop_name} SHOP! \nOur news channel: @{channel_name} \nHappy shopping!'
    ).format(shop_name=setting.shop_name, channel_name=setting.channel_name)

    assert fake_bot.get_message(user.user_id, text), "Не отправилось приветственное сообщение"

@pytest.mark.asyncio
async def test_maintenance_blocks_normal_user(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user
):
    from src.middlewares.aiogram_middleware import MaintenanceMiddleware

    fake_bot = replacement_fake_bot_fix

    user = await create_new_user()
    await update_settings(maintenance_mode=True)

    msg = FakeMessage(
        chat_id=user.user_id,
        username="user",
        id=user.user_id
    )

    mw = MaintenanceMiddleware()

    called = {"handler": False}

    async def handler(event, data):
        called["handler"] = True

    data = {
        "event_from_user": msg.from_user,
    }

    await mw(handler, msg, data)

    assert not called["handler"]
    assert fake_bot.get_message(
        user.user_id,
        get_text(
            user.language,
            'start_message',
            "The bot is temporarily unavailable due to maintenance. Please try again later"
        )
    )
