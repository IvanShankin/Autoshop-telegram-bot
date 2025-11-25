from types import SimpleNamespace

import pytest

from tests.helpers.fake_aiogram.fake_aiogram_module import FakeCallbackQuery, FakeFSMContext, FakeMessage
from src.utils.i18n import get_text


@pytest.mark.asyncio
async def test_safe_get_category_not_found_with_callback(
        monkeypatch,
        patch_fake_aiogram,
        replacement_fake_bot,
        create_new_user,
):
    """
    Если категория не найдена — handler должен удалить сообщение, отправить сообщение об этом и ничего не вернуть.
    """
    from src.modules.admin_actions.handlers.editor.category.import_handlers import safe_get_category

    async def fake_get(*args, **kwargs):
        return None

    monkeypatch.setattr("src.modules.admin_actions.handlers.editor.category.import_handlers",fake_get)

    user = await create_new_user()
    result = await safe_get_category(1, user)

    # ничего не возвращает
    assert result is None

    assert replacement_fake_bot.get_message(
        user.user_id,
        get_text(user.language, 'admins', "The category no longer exists")
    )

@pytest.mark.asyncio
async def test_show_category_sends_new_message(
        monkeypatch, patch_fake_aiogram, replacement_fake_bot,
        create_new_user, create_account_category
):
    from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category

    category = await create_account_category(is_accounts_storage=False)
    user = await create_new_user()

    await show_category(user, category.account_category_id, send_new_message=True)
    assert replacement_fake_bot.check_str_in_messages(category.name)


@pytest.mark.asyncio
async def test_show_category_update_data_edit(
        monkeypatch, patch_fake_aiogram, replacement_fake_bot,
        create_new_user, create_account_category
):
    from src.modules.admin_actions.handlers.editor.category.show_handlers import show_category_update_data

    category = await create_account_category()
    user = await create_new_user()

    callback = FakeCallbackQuery(data=f"id:{category.account_category_id}")
    callback.message = FakeMessage(message_id=50)

    await show_category_update_data(user, category.account_category_id, callback=callback)
    assert replacement_fake_bot.check_str_in_edited_messages(category.name)


@pytest.mark.asyncio
async def test_update_data_incorrect_value(
        monkeypatch, patch_fake_aiogram, replacement_fake_bot,
        create_new_user, create_account_category
):
    from src.modules.admin_actions.handlers.editor.category.update_handlers import update_data
    from src.modules.admin_actions.state.editor_categories import UpdateNumberInCategory

    category = await create_account_category()
    user = await create_new_user()
    state = FakeFSMContext()

    await state.update_data(category_id=category.account_category_id)
    await state.set_state(UpdateNumberInCategory.price)

    message = FakeMessage(text="не число")
    await update_data(message, state, user)

    assert replacement_fake_bot.check_str_in_messages(
        get_text(user.language, "miscellaneous", "Try again")
    )
    assert await state.get_state() == UpdateNumberInCategory.price.state


@pytest.mark.asyncio
async def test_update_data_valid_price(
        monkeypatch, patch_fake_aiogram, replacement_fake_bot,
        create_new_user, create_account_category
):
    from src.modules.admin_actions.handlers.editor.category.update_handlers import update_data
    from src.modules.admin_actions.state.editor_categories import UpdateNumberInCategory

    category = await create_account_category()
    user = await create_new_user()
    state = FakeFSMContext()
    await state.update_data(category_id=category.account_category_id)
    await state.set_state(UpdateNumberInCategory.price)

    message = FakeMessage(text="123")
    await update_data(message, state, user)
    assert replacement_fake_bot.check_str_in_messages(
        get_text(user.language, "miscellaneous", "Data updated successfully")
    )


@pytest.mark.asyncio
async def test_add_acc_category_name_prompts_next_language(
    monkeypatch,
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
):
    """
    Если при вводе имени категории остаются ещё языки (next_lang != None),
    то handler должен:
      - обновить state.requested_language
      - отправить сообщение с просьбой указать имя для следующего языка
      - установить state в GetDataForCategory.category_name
    """
    from src.modules.admin_actions.handlers.editor.category.create_handlers import add_acc_category_name
    from src.modules.admin_actions.state.editor_categories import GetDataForCategory

    user = await create_new_user()

    # подготовим state: пустые data_name -> next_lang должен быть первым в ALLOWED_LANGS
    state = FakeFSMContext()
    await state.update_data(
        service_id=1,
        parent_id=None,
        requested_language=GetDataForCategory.category_name.state,  # неважно, главное иметь ключи
        data_name={},
    )

    # имитируем сообщение с именем для DEFAULT_LANG
    msg = FakeMessage(text="My default name", chat_id=user.user_id, username=user.username)

    # вызов хендлера
    await add_acc_category_name(msg, state, user)

    # проверим, что state снова в ожидании имени (т.е. заполнение ещё не закончено)
    assert await state.get_state() == GetDataForCategory.category_name.state

    # Проверяем, что пользователю пришла подсказка о вводе следующего языка
    assert replacement_fake_bot.check_str_in_messages(
        get_text(
            user.language,
            "admins",
            "Specify the category name for this language: {language}"
        ).format(language="none")[:35]
    )


@pytest.mark.asyncio
async def test_service_update_index_updates_storage_flag(
    monkeypatch,
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
):
    """
    Если update_account_category проходит успешно, то флаг is_accounts_storage должен измениться в БД.
    Мы проверяем изменение напрямую через фабрику/базу данных.
    """
    from src.modules.admin_actions.handlers.editor.category.update_handlers import acc_category_update_storage
    from src.services.database.selling_accounts.actions import get_account_categories_by_category_id

    # создаём категорию (по умолчанию фабрика возвращает is_accounts_storage=False)
    category = await create_account_category(is_accounts_storage=False)
    user = await create_new_user()

    # подготовим callback: установить is_storage = 1
    cb = FakeCallbackQuery(data=f"acc_category_update_storage:{category.account_category_id}:1",
                           chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=777)

    # вызов handler'а
    await acc_category_update_storage(cb, user)

    # проверим, что в БД значение изменилось
    updated = await get_account_categories_by_category_id(
        account_category_id=category.account_category_id,
        language=user.language,
        return_not_show=True
    )
    assert updated is not None
    assert updated.is_accounts_storage is True


@pytest.mark.asyncio
async def test_delete_acc_category_success_edit_message(
    monkeypatch,
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
):
    """
    Успешное удаление категории должно привести к вызову edit_message
    с текстом 'Category successfully removed!'.
    """
    from src.modules.admin_actions.handlers.editor.category.delete_handlers import delete_acc_category

    category = await create_account_category()
    user = await create_new_user()

    cb = FakeCallbackQuery(data=f"delete_acc_category:{category.account_category_id}",
                           chat_id=user.user_id, username=user.username)
    cb.message = SimpleNamespace(message_id=321)

    await delete_acc_category(cb, user)

    # edit_message вызывается — ищем строку подтверждения
    assert replacement_fake_bot.check_str_in_edited_messages(
        get_text(user.language, 'admins', "Category successfully removed!")
    )


@pytest.mark.asyncio
async def test_update_category_image_non_image_document(
    monkeypatch,
    patch_fake_aiogram,
    replacement_fake_bot,
    create_new_user,
    create_account_category,
):
    """
    Если прислали документ с mime_type, который не начинается на 'image/',
    handler должен отправить пользователю сообщение с подсказкой.
    """
    from src.modules.admin_actions.handlers.editor.category.update_handlers import update_category_image

    category = await create_account_category()
    user = await create_new_user()

    # подготовим state с category_id
    state = FakeFSMContext()
    await state.update_data(category_id=category.account_category_id)

    # подготовим FakeMessage с документом не image/*
    doc = SimpleNamespace(mime_type="application/pdf", file_size=1024, file_id="file_123")
    msg = FakeMessage(text="", chat_id=user.user_id, username=user.username)
    msg.document = doc

    # вызов handler'а
    await update_category_image(msg, state, user)

    # проверяем, что юзеру отправили подсказку о том, что это не изображение
    expected = get_text(user.language, 'admins', "This is not an image. Send it as a document")
    assert replacement_fake_bot.get_message(user.user_id, expected)