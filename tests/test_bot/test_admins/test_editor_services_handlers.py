import asyncio
from types import SimpleNamespace

import pytest

from src.utils.i18n import get_text
from src.exceptions.service_exceptions import ServiceContainsCategories


@pytest.mark.asyncio
async def test_show_service_service_not_found(monkeypatch, patch_fake_aiogram, replacement_fake_bot):
    """
    Если get_account_service возвращает None — show_service должен ответить пользователю
    текстом 'The service is no longer available' (через callback.answer or send_message branch).
    """
    from src.modules.admin_actions.handlers.editor.service.editor_services_handlers import show_service

    user = SimpleNamespace(user_id=1111, language="ru")

    # подготовим callback-like объект: message.delete и answer — async функции
    called = {"answer": None, "deleted": False}

    async def fake_delete():
        called["deleted"] = True

    async def fake_answer(text, **kwargs):
        called["answer"] = text

    fake_callback = SimpleNamespace(
        message=SimpleNamespace(delete=fake_delete),
        answer=fake_answer
    )

    # get_account_service -> None
    async def fake_get_account_service(*args, **kwargs):
        return None

    from src.modules.admin_actions.handlers.editor.service import service_validator
    monkeypatch.setattr(service_validator, "get_account_service",  fake_get_account_service)

    # Вызов
    await show_service(user=user, service_id=999, callback=fake_callback)

    assert called["answer"] is not None
    assert get_text(user.language, 'admins', "The service is no longer available") in called["answer"]


@pytest.mark.asyncio
async def test_show_service_service_found_calls_edit_message(
        monkeypatch, patch_fake_aiogram, replacement_fake_bot, create_account_service, create_new_user
):
    """
    При наличии сервиса show_service должен вызвать edit_message/send_message с текстом, содержащим имя сервиса.
    """
    from src.modules.admin_actions.handlers.editor.service.editor_services_handlers import show_service
    service = await create_account_service(name="TelegramServiceX", index=7, show=True)
    user = await create_new_user()

    await show_service(user=user, service_id=service.account_service_id, send_new_message=False, message_id=123)

    message = get_text(
        user.language,
        'admins',
        "Service \n\nName: {name}\nIndex: {index}\nShow: {show}"
    ).format(name=service.name, index=service.index, show=service.show)

    assert replacement_fake_bot.get_edited_message(user.user_id, 123, message)


@pytest.mark.asyncio
async def test_delete_acc_service_success(
        monkeypatch, patch_fake_aiogram, replacement_fake_bot, create_account_service, create_new_user
):
    """
    Проверяет успешное удаление сервиса — сообщение 'Service successfully removed!'
    """
    from src.modules.admin_actions.handlers.editor.service.editor_services_handlers import delete_acc_service

    service = await create_account_service()
    user = await create_new_user()

    monkeypatch.setattr(
        "src.services.database.selling_accounts.actions.actions_delete.delete_account_service",
        lambda sid: asyncio.sleep(0),
    )

    callback = SimpleNamespace(
        data=f"delete_acc_service:{service.account_service_id}",
        from_user=SimpleNamespace(id=user.user_id),
        message=SimpleNamespace(message_id=777),
    )

    await delete_acc_service(callback, user)

    assert replacement_fake_bot.check_str_in_edited_messages(get_text(user.language, 'admins', "Service successfully removed"))


@pytest.mark.asyncio
async def test_delete_acc_service_contains_categories(
        monkeypatch, patch_fake_aiogram, replacement_fake_bot, create_account_service, create_new_user
):
    """
    Проверяет случай, когда при удалении выбрасывается ServiceContainsCategories —
    должно появиться сообщение 'The service has categories, delete them first'
    """
    from src.modules.admin_actions.handlers.editor.service.editor_services_handlers import delete_acc_service

    service = await create_account_service()
    user = await create_new_user()

    async def raise_contains(*_):
        raise ServiceContainsCategories()

    monkeypatch.setattr(
        "src.services.database.selling_accounts.actions.actions_delete.delete_account_service",
        raise_contains,
    )

    callback = SimpleNamespace(
        data=f"delete_acc_service:{service.account_service_id}",
        from_user=SimpleNamespace(id=user.user_id),
        message=SimpleNamespace(message_id=777),
    )

    await delete_acc_service(callback, user)

    text_expected = get_text(user.language, 'admins', "The service has categories, delete them first")

    assert replacement_fake_bot.check_str_in_edited_messages(text_expected)