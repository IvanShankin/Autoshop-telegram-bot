import os
import tempfile
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.exceptions import TextTooLong
from src.services.database.admins.models import SentMasMessages
from src.services.database.core import get_db


def test_visible_text_length_plain_text():
    from src.bot_actions.messages.mass_tg_mailing import visible_text_length

    assert visible_text_length("hello") == 5
    assert visible_text_length("<b>hello</b> world") == 11
    assert visible_text_length("<i><b>test</b></i>123") == 7
    assert visible_text_length("hello &amp; world") == len("hello & world")
    assert visible_text_length(None) == 0

@pytest.mark.asyncio
async def test_validate_inputs_success_without_photo(monkeypatch):
    from src.bot_actions.messages.mass_tg_mailing import validate_broadcast_inputs

    async def fake_get_photo(bot, admin_chat_id, photo_path):
        return None, None

    from src.bot_actions.messages import mass_tg_mailing as modul
    monkeypatch.setattr(
        modul,
        "get_photo_identifier",
        fake_get_photo
    )

    text, photo_id, photo_path, kb = await validate_broadcast_inputs(
        bot=None,
        admin_chat_id=1,
        text="Hello world",
    )

    assert text == "Hello world"
    assert photo_id is None
    assert kb is None

@pytest.mark.asyncio
async def test_validate_inputs_empty_text():
    from src.bot_actions.messages.mass_tg_mailing import validate_broadcast_inputs

    with pytest.raises(TextTooLong):
        await validate_broadcast_inputs(bot=None, admin_chat_id=1, text="   ")

@pytest.mark.asyncio
async def test_validate_inputs_text_too_long(monkeypatch):
    from src.bot_actions.messages.mass_tg_mailing import (
        validate_broadcast_inputs,
        TextTooLong,
        MAX_CHARS_WITHOUT_PHOTO,
    )

    long_text = "a" * (MAX_CHARS_WITHOUT_PHOTO + 10)

    with pytest.raises(TextTooLong):
        await validate_broadcast_inputs(
            bot=None,
            admin_chat_id=1,
            text=long_text,
        )

@pytest.mark.asyncio
async def test_validate_inputs_button_valid_url(monkeypatch):
    from src.bot_actions.messages.mass_tg_mailing import validate_broadcast_inputs

    async def fake_get_photo(bot, admin_chat_id, photo_path):
        return None, None

    from src.bot_actions.messages import mass_tg_mailing as modul
    monkeypatch.setattr(
        modul,
        "get_photo_identifier",
        fake_get_photo,
    )

    text, photo_id, photo_path, kb = await validate_broadcast_inputs(
        bot=None,
        admin_chat_id=1,
        text="hello",
        button_url="https://google.com",
    )

    assert kb is not None
    assert kb.inline_keyboard[0][0].url == "https://google.com"


@pytest.mark.asyncio
async def test_photo_id_success(monkeypatch, replacement_fake_bot_fix):
    from src.bot_actions.messages.mass_tg_mailing import get_photo_identifier

    # создаём временный файл
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.write(b"123")
    tmp.close()

    # fake send_photo → возвращает объект сообщения с .photo[-1].file_id
    async def fake_send_photo(chat_id, photo, caption):
        msg = SimpleNamespace(
            message_id=777,
            photo=[SimpleNamespace(file_id="FILE123")]
        )
        replacement_fake_bot_fix.sent.append(("send_photo", chat_id, photo, caption))
        return msg

    async def fake_delete(chat_id, message_id):
        replacement_fake_bot_fix.sent.append(("delete_message", chat_id, message_id))

    replacement_fake_bot_fix.send_photo = fake_send_photo
    replacement_fake_bot_fix.delete_message = fake_delete

    file_id, new_path = await get_photo_identifier(
        bot=replacement_fake_bot_fix,
        admin_chat_id=1,
        photo_path=tmp.name
    )

    assert file_id == "FILE123"


@pytest.mark.asyncio
async def test_broadcast_success_flow(
    replacement_fake_bot_fix,
    create_new_user,
    monkeypatch
):
    """
    Полный интеграционный тест:
    - 3 пользователя в БД
    - fake_bot успешно отправляет сообщения
    - проверяем, что генератор yield'ит успехи
    - проверяем запись SentMasMessages
    """
    from src.bot_actions.messages.mass_tg_mailing import broadcast_message_generator
    from src.bot_actions.messages import mass_tg_mailing as module

    admin_user = await create_new_user()
    second_user = await create_new_user()
    third_user = await create_new_user()

    # --- мок _send_single так, чтобы он был честным, но успешным ---
    async def fake_send_single(bot, user_id, text, photo_id, kb):
        # регистрируем отправку в fake_bot
        replacement_fake_bot_fix.sent.append(("send_message", user_id, text))
        return user_id, True, None

    monkeypatch.setattr(module, "_send_single", fake_send_single)

    # собираем результаты
    results = []
    async for uid, ok, exc in broadcast_message_generator(
        text="HELLO",
        admin_id=admin_user.user_id,
        photo_path=None,
        button_url=None,
    ):
        results.append((uid, ok, exc))

    # проверка результатов генератора
    assert len(results) == 3
    assert all(ok for _, ok, _ in results)
    assert set(uid for uid, _, _ in results) == {admin_user.user_id, second_user.user_id, third_user.user_id}

    # fake_bot получил 3 отправки
    assert len([x for x in replacement_fake_bot_fix.sent if x[0] == "send_message"]) == 3

    # Проверяем запись SentMasMessages
    async with get_db() as session_db:
        saved = (await session_db.execute(select(SentMasMessages))).scalar_one()
        assert saved.content == "HELLO"
        assert saved.number_received == 3
        assert saved.number_sent == 3


@pytest.mark.asyncio
async def test_broadcast_partial_fail(
    replacement_fake_bot_fix,
    create_new_user,
    monkeypatch
):
    """
    Тестируем ситуацию, когда часть отправок падает.
    """
    from src.bot_actions.messages.mass_tg_mailing import broadcast_message_generator
    from src.bot_actions.messages import mass_tg_mailing as module

    # Добавляем 3 юзеров
    admin_user = await create_new_user()
    second_user = await create_new_user()
    third_user = await create_new_user()

    # --- мок: один юзер падает ---
    async def fake_send_single(bot, user_id, text, photo_id, kb):
        if user_id == second_user.user_id:
            return user_id, False, RuntimeError("FAIL")
        replacement_fake_bot_fix.sent.append(("send_message", user_id, text))
        return user_id, True, None

    monkeypatch.setattr(module, "_send_single", fake_send_single)

    results = []
    async for uid, ok, exc in broadcast_message_generator(
        text="test",
        admin_id=admin_user.user_id,
    ):
        results.append((uid, ok, exc))

    # должны быть три результата
    assert len(results) == 3

    # успешные u1, u3 — не успешный u2
    ok_map = {uid: ok for uid, ok, _ in results}
    assert ok_map == {admin_user.user_id: True, second_user.user_id: False, third_user.user_id: True}

    async with get_db() as session_db:
        saved = (await session_db.execute(select(SentMasMessages))).scalar_one()
        assert saved.number_received == 2
        assert saved.number_sent == 3
        assert saved.content == "test"
