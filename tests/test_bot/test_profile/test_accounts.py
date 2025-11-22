from types import SimpleNamespace
from datetime import datetime, timedelta, UTC
import pytest

from src.config import DT_FORMAT
from src.utils.i18n import get_text
from src.utils.pars_number import e164_to_pretty
from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery



@pytest.mark.asyncio
async def test_get_file_for_login_with_existing_tg_media(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    create_tg_account_media,
):
    """
    Если TgAccountMedia уже содержит tdata_tg_id, функция должна попытаться отправить документ ботом
    и завершиться (не вызывать func_get_file).
    """
    from src.modules.profile.handlers.accounts_handlers import get_file_for_login

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    # создаём TgAccountMedia с уже заполненным tdata_tg_id
    await create_tg_account_media(
        account_storage_id=sold_full.account_storage.account_storage_id,
        tdata_tg_id="EXISTING_FILE_ID",
        session_tg_id=None
    )

    # func_get_file сделаем генератором, который бы упал если вызван (так поймём, что не был вызван)
    async def func_get_file_should_not_be_called(_):
        raise RuntimeError("func_get_file was called unexpectedly")
        if False:
            yield None

    cb = FakeCallbackQuery(data=f"get_file_for_login:{sold_full.sold_account_id}", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=11)

    await get_file_for_login(cb, func_get_file_should_not_be_called, type_media="tdata_tg_id")

    # проверяем что бот попытался отправить
    sent = replacement_fake_bot.sent
    assert len(sent) > 0
    assert sent[0][0] == user.user_id


@pytest.mark.asyncio
async def test_get_file_for_login_without_prior_file_calls_func_and_updates_media(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    create_tg_account_media,
    tmp_path,
):
    """
    Если tg_media существует но поле tdata_tg_id пустое, должно быть:
    - отправлен документ, взятый из func_get_file
    - update_tg_account_media должен получить новый file_id (реальное обновление происходит через fixture)
    """
    from src.modules.profile.handlers.accounts_handlers import get_file_for_login, get_tg_account_media

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    # создаём TgAccountMedia *сущность* в БД, но без file id (чтобы код обновил запись)
    tg_media = await create_tg_account_media(
        account_storage_id=sold_full.account_storage.account_storage_id,
        tdata_tg_id=None,
        session_tg_id=None
    )

    # создаём реальный файл путь, который func_get_file будет отдавать
    file_on_disk = tmp_path / "archive_to_send.zip"
    file_on_disk.write_bytes(b"dummy-zip-content")

    async def func_get_file(_account_storage):
        # yield путь как делает реальная функция
        yield str(file_on_disk)

    cb = FakeCallbackQuery(data=f"get_file_for_login:{sold_full.sold_account_id}", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=33)

    # вызов
    await get_file_for_login(cb, func_get_file, type_media="tdata_tg_id")

    # проверяем, что бот отправил документ
    sent = replacement_fake_bot.sent
    assert any(call[0] == user.user_id for call in sent), "Bot did not send document after func_get_file"

    # Проверим, что запись tg_media теперь содержит непустой tdata_tg_id
    updated = await get_tg_account_media(sold_full.account_storage.account_storage_id)
    assert updated.tdata_tg_id is not None


@pytest.mark.asyncio
async def test_get_code_acc_returns_codes_and_sends_message(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    monkeypatch,
):
    """Позитивный сценарий"""
    from src.modules.profile.handlers.accounts_handlers import get_code_acc

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    now = datetime.now(UTC)
    # Мокаем только get_auth_codes
    sample = [
        (now - timedelta(minutes=2), "11111"),
        (now - timedelta(minutes=1), "22222"),
    ]
    async def fake_get_auth_codes(*_a, **_kw):
        return sample

    result_message = ''
    for date, code in sample:
        result_message += get_text(
            user.language,
            'profile_messages',
            "Date: {date} \nCode: <code>{code}</code>\n\n"
        ).format(date=date.strftime(DT_FORMAT), code=code)

    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.get_auth_codes", fake_get_auth_codes)

    cb = FakeCallbackQuery(data=f"get_code_acc:{sold_full.sold_account_id}", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=1)

    # Выполняем
    await get_code_acc(cb, user)
    assert replacement_fake_bot.get_message(user.user_id, result_message)


@pytest.mark.asyncio
async def test_get_code_acc_returns_false_shows_unable_to_retrieve(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    monkeypatch,
):
    """
    Если get_auth_codes возвращает False — должен показаться alert "Unable to retrieve data".
    """
    from src.modules.profile.handlers.accounts_handlers import get_code_acc

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    async def fake_get_auth_codes(*_a, **_kw):
        return False
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.get_auth_codes", fake_get_auth_codes)

    cb = FakeCallbackQuery(data=f"get_code_acc:{sold_full.sold_account_id}", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=2)

    answered = {}
    async def fake_answer(text, **kwargs):
        answered["text"] = text
        answered["kw"] = kwargs

    cb.answer = fake_answer
    await get_code_acc(cb, user)
    assert get_text(user.language, 'profile_messages', "Unable to retrieve data") in answered["text"]


@pytest.mark.asyncio
async def test_get_code_acc_no_codes_found_alert(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    monkeypatch,
):
    """
    Если get_auth_codes возвращает пустой список -> alert 'No codes found'.
    """
    from src.modules.profile.handlers.accounts_handlers import get_code_acc

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    async def fake_get_auth_codes(*_a, **_kw):
        return []
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.get_auth_codes", fake_get_auth_codes)

    cb = FakeCallbackQuery(data=f"get_code_acc:{sold_full.sold_account_id}", chat_id=user.user_id)
    cb.message = SimpleNamespace(message_id=3)

    answered = {}
    async def fake_answer(text, **kwargs):
        answered["text"] = text
        answered["kw"] = kwargs

    cb.answer = fake_answer
    await get_code_acc(cb, user)
    assert get_text(user.language, 'profile_messages', "No codes found") in answered["text"]



@pytest.mark.asyncio
async def test_chek_valid_acc_valid_true_no_change(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    monkeypatch,
):
    """
    Проверка при result=True и совпадающей валидности — просто alert с текстом "The account is valid".
    """
    from src.modules.profile.handlers.accounts_handlers import chek_valid_acc

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    # мокаем check_account_validity
    async def fake_check_account_validity(*_a, **_kw):
        return True
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.check_account_validity", fake_check_account_validity)

    cb = FakeCallbackQuery(
        data=f"chek_valid_acc:{sold_full.sold_account_id}:{sold_full.type_account_service_id}:1:1",
        chat_id=user.user_id
    )
    cb.message = SimpleNamespace(message_id=10)

    answered = {}
    async def fake_answer(text, **kwargs):
        answered["text"] = text
        answered["kw"] = kwargs
    cb.answer = fake_answer

    await chek_valid_acc(cb, user)

    assert get_text(user.language, 'profile_messages', 'The account is valid') in answered["text"]


@pytest.mark.asyncio
async def test_chek_valid_acc_valid_false_updates_and_refreshes_card(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    monkeypatch,
):
    """
    Проверка при result=False и изменении валидности — должен обновить запись и вызвать show_sold_account.
    """
    from src.modules.profile.handlers.accounts_handlers import chek_valid_acc

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    called = {}

    async def fake_check_account_validity(*_a, **_kw):
        return False
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.check_account_validity", fake_check_account_validity)

    async def fake_show_sold_account(**kw):
        called["show_sold_account"] = kw
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.show_sold_account", fake_show_sold_account)

    cb = FakeCallbackQuery(
        data=f"chek_valid_acc:{sold_full.sold_account_id}:{sold_full.type_account_service_id}:1:1",
        chat_id=user.user_id
    )
    cb.message = SimpleNamespace(message_id=12)

    answered = {}
    async def fake_answer(text, **kwargs):
        answered["text"] = text
        answered["kw"] = kwargs
    cb.answer = fake_answer

    await chek_valid_acc(cb, user)

    assert get_text(user.language, 'profile_messages', 'The account is not valid') in answered["text"]
    assert "show_sold_account" in called


@pytest.mark.asyncio
async def test_confirm_del_acc_edits_message(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
):
    """
    Проверяем, что confirm_del_acc вызывает edit_message с нужным текстом.
    """
    from src.modules.profile.handlers.accounts_handlers import confirm_del_acc

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id, phone_number="+123456789")

    cb = FakeCallbackQuery(
        data=f"confirm_del_acc:{sold_full.sold_account_id}:{sold_full.type_account_service_id}:2",
        chat_id=user.user_id
    )
    cb.message = SimpleNamespace(message_id=20)

    await confirm_del_acc(cb, user)

    text = get_text(user.language, 'profile_messages',
        "Confirm deletion of this account?\n\n"
        "Phone number: {phone_number}\n"
        "Name: {name}"
    ).format(
        phone_number=e164_to_pretty(sold_full.account_storage.phone_number),
        name=sold_full.name,
    )
    assert replacement_fake_bot.get_edited_message(user.user_id, message_id=20, message=text)


@pytest.mark.asyncio
async def test_del_account_successful_flow(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    monkeypatch,
):
    """
    Проверяем успешное удаление аккаунта: move_in_account -> True,
    должно вызвать show_all_sold_account и alert с текстом "The account has been successfully deleted".
    """
    from src.modules.profile.handlers.accounts_handlers import del_account

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    called = {}

    async def fake_move_in_account(*_a, **_kw):
        return True
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.move_in_account", fake_move_in_account)

    async def fake_show_all_sold_account(**kw):
        called["show_all_sold_account"] = kw
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.show_all_sold_account", fake_show_all_sold_account)

    cb = FakeCallbackQuery(
        data=f"del_account:{sold_full.sold_account_id}:{sold_full.type_account_service_id}:3",
        chat_id=user.user_id
    )
    cb.message = SimpleNamespace(message_id=30)

    answered = {}
    async def fake_answer(text, **kwargs):
        answered["text"] = text
        answered["kw"] = kwargs
    cb.answer = fake_answer

    await del_account(cb, user)

    assert get_text(user.language, 'profile_messages', "The account has been successfully deleted") in answered["text"]
    assert "show_all_sold_account" in called


@pytest.mark.asyncio
async def test_del_account_move_in_account_fails_shows_alert(
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_sold_account,
    monkeypatch,
):
    """
    Проверяем, что если move_in_account возвращает False — вызывается alert "An error occurred, please try again".
    """
    from src.modules.profile.handlers.accounts_handlers import del_account

    user = await create_new_user()
    sold_small, sold_full = await create_sold_account(owner_id=user.user_id)

    async def fake_move_in_account(*_a, **_kw):
        return False
    monkeypatch.setattr("src.modules.profile.handlers.accounts_handlers.move_in_account", fake_move_in_account)

    cb = FakeCallbackQuery(
        data=f"del_account:{sold_full.sold_account_id}:{sold_full.type_account_service_id}:5",
        chat_id=user.user_id
    )
    cb.message = SimpleNamespace(message_id=31)

    answered = {}
    async def fake_answer(text, **kwargs):
        answered["text"] = text
        answered["kw"] = kwargs
    cb.answer = fake_answer

    await del_account(cb, user)

    assert get_text(user.language, 'profile_messages', "An error occurred, please try again") in answered["text"]
