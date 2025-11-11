import pytest
from types import SimpleNamespace
from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery


@pytest.mark.asyncio
async def test_my_voucher_callback(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_voucher,
):
    """
    my_voucher:<page> — бот редактирует сообщение со списком ваучеров.
    """
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    # создаём ваучер для пользователя
    voucher = await create_voucher(creator_id=user.user_id)

    cb = FakeCallbackQuery(data="my_voucher:1", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=7)

    await module.my_voucher(cb, user)

    i18n = module.get_i18n(user.language, 'profile_messages')
    expected = i18n.gettext("All vouchers. To view a specific voucher, click on it")

    assert fake_bot.get_edited_message(user.user_id, 7, expected), "Не отредактировалось сообщение о просмотре ваучеров"



@pytest.mark.asyncio
async def test_show_voucher_inactive(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_voucher,
):
    """Callback 'show_voucher:<id>:<page>' — невалидный ваучер должен вызвать сообщение об ошибке."""
    from src.modules.profile.handlers import transfer_balance_handler as module\

    fake_bot = replacement_fake_bot
    user = await create_new_user()

    voucher = await create_voucher(creator_id=user.user_id, is_valid=False)

    cb = FakeCallbackQuery(data=f"show_voucher:{voucher.voucher_id}:1", chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=10)

    await module.show_voucher(cb, user)

    i18n = module.get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('This voucher is currently inactive, please select another one')
    assert fake_bot.get_edited_message(user.user_id, 10, text), "Не отправилось сообщение о неактивном ваучере"


@pytest.mark.asyncio
async def test_show_voucher_active_success(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_voucher,
    create_new_user,
):
    """Callback 'show_voucher:<id>:<page>' — активный ваучер корректно отображается."""
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot
    voucher = await create_voucher()
    user = await create_new_user()

    cb = FakeCallbackQuery(data=f"show_voucher:{voucher.voucher_id}:1", chat_id=voucher.creator_id)
    cb.message = SimpleNamespace(message_id=77)

    await module.show_voucher(cb, user)

    assert fake_bot.check_str_in_edited_messages(f"ID: {voucher.voucher_id}"), \
        "Не отобразилась информация об активном ваучере"


@pytest.mark.asyncio
async def test_confirm_deactivate_voucher_inactive(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_voucher,
):
    """Callback 'confirm_deactivate_voucher' — если ваучер невалиден, бот сообщает об этом."""
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()

    voucher = await create_voucher(creator_id=user.user_id, is_valid=False)

    cb = FakeCallbackQuery(data=f"confirm_deactivate_voucher:{voucher.voucher_id}:1", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=88)

    await module.confirm_deactivate_voucher(cb, user)

    i18n = module.get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('This voucher is currently inactive')
    assert fake_bot.get_edited_message(user.user_id, 88, text), \
        "Не отправилось сообщение о неактивном ваучере при подтверждении"


@pytest.mark.asyncio
async def test_confirm_deactivate_voucher_active_success(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_voucher,
    create_new_user,
):
    """Callback 'confirm_deactivate_voucher' — активный ваучер вызывает запрос подтверждения."""
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot
    voucher = await create_voucher()
    user = await create_new_user()

    cb = FakeCallbackQuery(data=f"confirm_deactivate_voucher:{voucher.voucher_id}:1", chat_id=voucher.creator_id)
    cb.message = SimpleNamespace(message_id=44)

    await module.confirm_deactivate_voucher(cb, user)

    i18n = module.get_i18n("ru", 'profile_messages')
    text_part = i18n.gettext("Are you sure you want to deactivate the voucher?")
    assert fake_bot.check_str_in_edited_messages(text_part), \
        "Не появилось сообщение о подтверждении деактивации ваучера"


@pytest.mark.asyncio
async def test_deactivate_voucher_inactive(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_voucher,
):
    """Callback 'deactivate_voucher' — если ваучер невалиден, бот сообщает об этом."""
    from src.modules.profile.handlers import transfer_balance_handler as module

    fake_bot = replacement_fake_bot
    user = await create_new_user()
    voucher = await create_voucher(creator_id=user.user_id, is_valid=False)

    cb = FakeCallbackQuery(data=f"deactivate_voucher:{voucher.voucher_id}:1", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=55)

    await module.deactivate_voucher(cb, user)

    i18n = module.get_i18n(user.language, 'profile_messages')
    text = i18n.gettext('This voucher is currently inactive')
    assert fake_bot.get_edited_message(user.user_id, 55, text), \
        "Не отправилось сообщение о неактивном ваучере при деактивации"


@pytest.mark.asyncio
async def test_deactivate_voucher_success(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_voucher,
    create_new_user,
):
    """Callback 'deactivate_voucher' — успешная деактивация ваучера."""
    from src.modules.profile.handlers import transfer_balance_handler as module

    user = await create_new_user()
    fake_bot = replacement_fake_bot
    voucher = await create_voucher()

    cb = FakeCallbackQuery(data=f"deactivate_voucher:{voucher.voucher_id}:1", chat_id=voucher.creator_id)
    cb.message = SimpleNamespace(message_id=66)

    await module.deactivate_voucher(cb, user)

    i18n = module.get_i18n("en", 'profile_messages')
    text = i18n.gettext("The voucher has been successfully deactivated")
    assert fake_bot.check_str_in_edited_messages(text), \
        "Не отправилось сообщение об успешной деактивации ваучера"
