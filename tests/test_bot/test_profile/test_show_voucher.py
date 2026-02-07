import pytest
from types import SimpleNamespace

from src.config import get_config
from src.utils.i18n import get_text
from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery


@pytest.mark.asyncio
async def test_voucher_list_callback(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_voucher,
):
    """
    voucher_list:<page> — бот редактирует сообщение со списком ваучеров.
    """
    from src.modules.profile.handlers.vouchers_handlers import voucher_list

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    # создаём ваучер для пользователя
    voucher = await create_voucher(creator_id=user.user_id)

    cb = FakeCallbackQuery(data=f"voucher_list:{user.user_id}:1", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=7)

    await voucher_list(cb, user)

    expected = get_text(user.language, "profile_messages", "all_vouchers_list")

    assert fake_bot.get_edited_message(user.user_id, 7, expected), "Не отредактировалось сообщение о просмотре ваучеров"



@pytest.mark.asyncio
async def test_show_voucher_inactive(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_voucher,
):
    """Callback 'show_voucher:<id>:<page>' — невалидный ваучер должен вызвать сообщение об ошибке."""
    from src.modules.profile.handlers.vouchers_handlers import show_voucher

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()

    voucher = await create_voucher(creator_id=user.user_id, is_valid=False)

    cb = FakeCallbackQuery(data=f"show_voucher:{user.user_id}:1:{voucher.voucher_id}", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=10)

    await show_voucher(cb, user)

    text = get_text(user.language, "profile_messages", "voucher_currently_inactive")
    assert fake_bot.get_edited_message(user.user_id, 10, text), "Не отправилось сообщение о неактивном ваучере"


@pytest.mark.asyncio
async def test_show_voucher_active_success(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_voucher,
    create_new_user,
):
    """Callback 'show_voucher:<id>:<page>' — активный ваучер корректно отображается."""
    from src.modules.profile.handlers.vouchers_handlers import show_voucher

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    voucher = await create_voucher(creator_id=user.user_id)

    cb = FakeCallbackQuery(data=f"show_voucher:{user.user_id}:1:{voucher.voucher_id}", chat_id=voucher.creator_id)
    cb.message = SimpleNamespace(message_id=77)

    await show_voucher(cb, user)

    assert fake_bot.check_str_in_edited_messages(f"ID: {voucher.voucher_id}"), \
        "Не отобразилась информация об активном ваучере"


@pytest.mark.asyncio
async def test_confirm_deactivate_voucher_inactive(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_voucher,
):
    """Callback 'confirm_deactivate_voucher' — если ваучер невалиден, бот сообщает об этом."""
    from src.modules.profile.handlers.vouchers_handlers import confirm_deactivate_voucher

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()

    voucher = await create_voucher(creator_id=user.user_id, is_valid=False)

    cb = FakeCallbackQuery(data=f"confirm_deactivate_voucher:{voucher.voucher_id}:1", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=88)

    await confirm_deactivate_voucher(cb, user)

    text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
    assert fake_bot.get_edited_message(user.user_id, 88, text), \
        "Не отправилось сообщение о неактивном ваучере при подтверждении"


@pytest.mark.asyncio
async def test_confirm_deactivate_voucher_active_success(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_voucher,
    create_new_user,
):
    """Callback 'confirm_deactivate_voucher' — активный ваучер вызывает запрос подтверждения."""
    from src.modules.profile.handlers.vouchers_handlers import confirm_deactivate_voucher

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    voucher = await create_voucher(creator_id=user.user_id)

    cb = FakeCallbackQuery(data=f"confirm_deactivate_voucher:{voucher.voucher_id}:1", chat_id=voucher.creator_id)
    cb.message = SimpleNamespace(message_id=44)

    await confirm_deactivate_voucher(cb, user)

    text_part = get_text(
        'ru',
        "profile_messages",
        "confirmation_deactivate_voucher"
    ).format(amount=voucher.amount)
    assert fake_bot.check_str_in_edited_messages(text_part), \
        "Не появилось сообщение о подтверждении деактивации ваучера"


@pytest.mark.asyncio
async def test_deactivate_voucher_inactive(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_new_user,
    create_voucher,
):
    """Callback 'deactivate_voucher' — если ваучер невалиден, бот сообщает об этом."""
    from src.modules.profile.handlers.vouchers_handlers import deactivate_voucher

    fake_bot = replacement_fake_bot_fix
    user = await create_new_user()
    voucher = await create_voucher(creator_id=user.user_id, is_valid=False)

    cb = FakeCallbackQuery(data=f"deactivate_voucher:{voucher.voucher_id}:1", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=55)

    await deactivate_voucher(cb, user)

    text = get_text(user.language, "profile_messages", 'voucher_currently_inactive')
    assert fake_bot.get_edited_message(user.user_id, 55, text), \
        "Не отправилось сообщение о неактивном ваучере при деактивации"


@pytest.mark.asyncio
async def test_deactivate_voucher_success(
    patch_fake_aiogram,
    replacement_fake_bot_fix,
    create_voucher,
    create_new_user,
):
    """Callback 'deactivate_voucher' — успешная деактивация ваучера."""
    from src.modules.profile.handlers.vouchers_handlers import deactivate_voucher

    user = await create_new_user()
    fake_bot = replacement_fake_bot_fix
    voucher = await create_voucher(creator_id=user.user_id)

    cb = FakeCallbackQuery(data=f"deactivate_voucher:{voucher.voucher_id}:1", chat_id=voucher.creator_id)
    cb.message = SimpleNamespace(message_id=66)

    await deactivate_voucher(cb, user)

    text = get_text('en', "profile_messages", "voucher_successfully_deactivated")
    assert fake_bot.check_str_in_edited_messages(text), \
        "Не отправилось сообщение об успешной деактивации ваучера"
