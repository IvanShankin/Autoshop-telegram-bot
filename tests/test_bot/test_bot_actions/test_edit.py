import pytest

from tests.helpers.fake_aiogram.fake_aiogram_module import SpySend


class TestEditMessage:
    @pytest.mark.asyncio
    async def test_edit_media_by_file_id_success(self, patch_fake_aiogram, replacement_fake_bot_fix,  monkeypatch, create_ui_image):
        """
        Если ui_image.file_id есть и bot.edit_message_media по file_id проходит успешно,
        то edit_message должен успешно завершиться и НЕ вызывать send_message.
        """
        from src.bot_actions.messages import edit as bot_actions

        ui_image, _ = await create_ui_image(key="test_key", show=True, file_id="existing_file_id")
        bot = replacement_fake_bot_fix
        spy_send = SpySend()

        monkeypatch.setattr(bot_actions, "send_message", spy_send)

        # Вызов
        await bot_actions.edit_message(
            chat_id=42,
            message_id=100,
            message="New caption",
            image_key="test_key",
            fallback_image_key=None,
            reply_markup=None
        )

        # Проверки: edit_message_media вызван, send_message не вызван
        assert any(c[0] == "edit_message_media" for c in bot.calls)
        assert spy_send.calls == []


    @pytest.mark.asyncio
    async def test_edit_text_message_not_modified(self, patch_fake_aiogram, replacement_fake_bot_fix, monkeypatch):
        """
        Если edit_message_text бросает TelegramBadRequest('message is not modified') —
        это не ошибка: send_message не вызывается.
        """
        from src.bot_actions.messages import edit as bot_actions
        from aiogram import exceptions as aiogram_excs
        not_modified_exc = aiogram_excs.TelegramBadRequest("message is not modified")

        bot = replacement_fake_bot_fix
        bot.edit_text_behavior = not_modified_exc
        spy_send = SpySend()

        monkeypatch.setattr(bot_actions, "send_message", spy_send)

        await bot_actions.edit_message(
            chat_id=1,
            message_id=2,
            message="Same text",
            image_key=None,
            fallback_image_key=None,
            reply_markup=None
        )

        assert any(c[0] == "edit_message_text" for c in bot.calls)
        assert spy_send.calls == []


    @pytest.mark.asyncio
    async def test_edit_text_message_not_found_fallbacks_to_send(self, patch_fake_aiogram, replacement_fake_bot_fix, monkeypatch):
        """
        Если edit_message_text бросает TelegramBadRequest('message not found'),
        то должно произойти fallback-отправление через send_message.
        """
        from src.bot_actions.messages import edit as bot_actions
        from aiogram import exceptions as aiogram_excs

        not_found_exc = aiogram_excs.TelegramBadRequest("message not found")
        bot = replacement_fake_bot_fix
        bot.edit_text_behavior = not_found_exc

        spy_send = SpySend()

        monkeypatch.setattr(bot_actions, "send_message", spy_send)

        await bot_actions.edit_message(
            chat_id=11,
            message_id=12,
            message="This will fallback",
            image_key=None,
            fallback_image_key=None,
            reply_markup=None
        )

        assert any(c[0] == "edit_message_text" for c in bot.calls)
        assert len(spy_send.calls) == 1
        assert spy_send.calls[0][0] == 11
        assert "This will fallback" in spy_send.calls[0][1]


    @pytest.mark.asyncio
    async def test_local_file_missing_then_fallback_send(
            self, patch_fake_aiogram, replacement_fake_bot_fix, monkeypatch, create_ui_image, tmp_path
    ):
        """
        Симулируем отсутствие локального файла (FileNotFoundError при создании FSInputFile)
        и убеждаемся, что происходит fallback: send_message вызывается.
        """
        from src.bot_actions.messages import edit as bot_actions
        ui_image, _ = await create_ui_image(key="missing_local", show=True, file_id=None)
        # делаем несуществующий путь
        ui_image.file_name = "no_such_file.png"

        # Подменим FSInputFile в модуле на функцию, которая бросает FileNotFoundError
        def fake_FSInputFile(path):
            raise FileNotFoundError(f"No such file: {path}")

        spy_send = SpySend()

        monkeypatch.setattr(bot_actions, "FSInputFile", fake_FSInputFile)
        monkeypatch.setattr(bot_actions, "send_message", spy_send)

        await bot_actions.edit_message(
            chat_id=900,
            message_id=901,
            message="Trying to upload missing file",
            image_key="missing_local",
            fallback_image_key=None,
            reply_markup=None
        )

        # Т.к. upload не удался — должен быть фоллбэк на send_message
        assert len(spy_send.calls) == 1
        assert spy_send.calls[0][0] == 900
        assert "Trying to upload missing file" in spy_send.calls[0][1]
