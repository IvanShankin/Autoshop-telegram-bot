from types import SimpleNamespace
import pytest

from tests.helpers.fake_aiogram.fake_aiogram_module import FakeTelegramBadRequest, SpySend


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_with_valid_file_id(self, patch_fake_aiogram, replacement_fake_bot, create_ui_image, monkeypatch):
        """Валидный file_id: отправляется фото без загрузки"""
        from src.bot_actions.messages import send_message
        fake_bot = replacement_fake_bot
        ui_image, _ = await create_ui_image(key="welcome", file_id='existing_file_id')

        await send_message(chat_id=123, message="Hello!", image_key="welcome", fallback_image_key=None)

        assert len(fake_bot.sent) == 1
        chat_id, caption, kwargs = fake_bot.sent[0]
        assert caption == "Hello!"
        assert chat_id == 123


    @pytest.mark.asyncio
    async def test_send_message_with_invalid_file_id(
        self, patch_fake_aiogram, replacement_fake_bot, create_ui_image, monkeypatch, tmp_path
    ):
        """Недействительный file_id — fallback на загрузку файла с диска"""
        from src.bot_actions.messages import send_message
        fake_bot = replacement_fake_bot

        # Подготовим подмену MEDIA_DIR, чтобы send_message открыл файл по правильному пути
        media_dir = tmp_path / "media"
        ui_sections = media_dir / "ui_sections"
        ui_sections.mkdir(parents=True, exist_ok=True)

        # Создаём ui_image и сам файл
        ui_image, file_abs = await create_ui_image(key="error_case", file_id="bad_file_id")

        # Перемещаем тестовый файл туда, где send_message его ожидает
        target_path = media_dir / ui_image.file_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"fake-image-bytes")

        # --- Мокаем bot.send_photo ---
        async def fake_send_photo(chat_id, photo, caption="", **kwargs):
            if photo == "bad_file_id":
                raise Exception("Bad Request: file not found")
            fake_bot.sent.append((chat_id, caption, photo, kwargs))
            # имитация успешного сообщения с новым file_id
            return SimpleNamespace(photo=[SimpleNamespace(file_id="new_file_id_123")])

        fake_bot.send_photo = fake_send_photo

        # Мокаем update_ui_image, чтобы проверить, что file_id обновился
        updated = {}

        async def fake_update_ui_image(**kwargs):
            updated.update(kwargs)

        from src.bot_actions.messages import edit as modul
        monkeypatch.setattr(modul, "update_ui_image", fake_update_ui_image)

        # --- Запуск ---
        await send_message(chat_id=321, message="Reupload test", image_key="error_case", fallback_image_key=None)

        # --- Проверки ---
        assert len(fake_bot.sent) == 1, "Ожидалось одно успешное сообщение после fallback"
        chat_id, caption, photo, kwargs = fake_bot.sent[0]
        assert caption == "Reupload test"
        assert isinstance(photo, (str, bytes)) or hasattr(photo, "read"), "photo должен быть файлом или id"
        assert "new_file_id" in updated["file_id"]
        assert chat_id == 321



    @pytest.mark.asyncio
    async def test_send_message_with_show_false(
        self, patch_fake_aiogram, replacement_fake_bot, create_ui_image
    ):
        """ show=False — фото не отправляется, только текст"""
        from src.bot_actions.messages import send_message

        fake_bot = replacement_fake_bot
        ui_image, _ = await create_ui_image(key="hidden_img", show=False, file_id="file123")

        await send_message(chat_id=777, message="Hidden image", image_key="hidden_img", fallback_image_key=None)

        assert len(fake_bot.sent) == 2 # 2 т.к. ещё отправляется сообщение о проверке аккаунтов
        chat_id, text, kwargs = fake_bot.sent[1]
        assert text == "Hidden image"
        assert chat_id == 777


    @pytest.mark.asyncio
    async def test_send_message_no_image_found(
        self, patch_fake_aiogram, replacement_fake_bot, monkeypatch
    ):
        """ Нет изображения по ключу — отправляется обычный текст"""
        from src.bot_actions.messages import send_message

        fake_bot = replacement_fake_bot

        async def fake_get_ui_image(key: str):
            return None

        from src.bot_actions.messages import edit as modul
        monkeypatch.setattr(modul, "get_ui_image", fake_get_ui_image)

        await send_message(chat_id=555, message="Plain text", image_key="missing")

        assert len(fake_bot.sent) == 2 # 2 т.к. ещё отправляется сообщение о проверке аккаунтов
        chat_id, text, kwargs = fake_bot.sent[1]
        assert text == "Plain text"
        assert chat_id == 555


    @pytest.mark.asyncio
    async def test_send_message_without_image_key(
        self, patch_fake_aiogram, replacement_fake_bot
    ):
        """Без image_key — просто сообщение"""
        from src.bot_actions.messages import send_message

        fake_bot = replacement_fake_bot

        await send_message(chat_id=999, message="Simple text")

        assert len(fake_bot.sent) == 1
        chat_id, text, kwargs = fake_bot.sent[0]
        assert text == "Simple text"
        assert chat_id == 999


class TestEditMessage:
    @pytest.mark.asyncio
    async def test_edit_media_by_file_id_success(self, patch_fake_aiogram, replacement_fake_bot,  monkeypatch, create_ui_image):
        """
        Если ui_image.file_id есть и bot.edit_message_media по file_id проходит успешно,
        то edit_message должен успешно завершиться и НЕ вызывать send_message.
        """
        from src.bot_actions.messages import edit as bot_actions

        ui_image, _ = await create_ui_image(key="test_key", show=True, file_id="existing_file_id")
        bot = replacement_fake_bot
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
    async def test_file_id_invalid_then_upload_succeeds_and_update_ui_image(
            self, patch_fake_aiogram, replacement_fake_bot, monkeypatch, create_ui_image
    ):
        """
        Если file_id невалиден (TelegramBadRequest с текстом file not found),
        то сначала будет попытка _try_edit_media_by_file_id (упадёт), затем upload (успех),
        и update_ui_image должен быть вызван с новым file_id.
        """
        from src.bot_actions.messages import edit as bot_actions
        ui_image, _ = await create_ui_image(key="upl_key", show=True, file_id="invalid_file_id")

        bot = replacement_fake_bot
        # поведение: первая попытка edit_message_media бросает TelegramBadRequest, вторая возвращает msg с photo
        call_count = {"n": 0}

        async def edit_media_behavior(chat_id, message_id, media, reply_markup=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise FakeTelegramBadRequest("file not found on telegram servers")
            return SimpleNamespace(photo=[SimpleNamespace(file_id="fresh_file_id")])

        bot.edit_media_behavior = edit_media_behavior

        updated = {}
        async def fake_update_ui_image(key, show, file_id):
            updated['args'] = (key, show, file_id)
            return None

        spy_send = SpySend()

        monkeypatch.setattr(bot_actions, "update_ui_image", fake_update_ui_image)
        monkeypatch.setattr(bot_actions, "send_message", spy_send)

        await bot_actions.edit_message(
            chat_id=7,
            message_id=77,
            message="Caption after trying both",
            image_key="upl_key",
            fallback_image_key=None,
            reply_markup=None
        )

        # Проверки
        assert any(c[0] == "edit_message_media" for c in bot.calls)
        assert updated.get('args') == ("upl_key", ui_image.show, "fresh_file_id")
        assert spy_send.calls == []


    @pytest.mark.asyncio
    async def test_edit_text_message_not_modified(self, patch_fake_aiogram, replacement_fake_bot, monkeypatch):
        """
        Если edit_message_text бросает TelegramBadRequest('message is not modified') —
        это не ошибка: send_message не вызывается.
        """
        from src.bot_actions.messages import edit as bot_actions
        from aiogram import exceptions as aiogram_excs
        not_modified_exc = aiogram_excs.TelegramBadRequest("message is not modified")

        bot = replacement_fake_bot
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
    async def test_edit_text_message_not_found_fallbacks_to_send(self, patch_fake_aiogram, replacement_fake_bot, monkeypatch):
        """
        Если edit_message_text бросает TelegramBadRequest('message not found'),
        то должно произойти fallback-отправление через send_message.
        """
        from src.bot_actions.messages import edit as bot_actions
        from aiogram import exceptions as aiogram_excs

        not_found_exc = aiogram_excs.TelegramBadRequest("message not found")
        bot = replacement_fake_bot
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
            self, patch_fake_aiogram, replacement_fake_bot, monkeypatch, create_ui_image, tmp_path
    ):
        """
        Симулируем отсутствие локального файла (FileNotFoundError при создании FSInputFile)
        и убеждаемся, что происходит fallback: send_message вызывается.
        """
        from src.bot_actions.messages import edit as bot_actions
        ui_image, _ = await create_ui_image(key="missing_local", show=True, file_id=None)
        # делаем несуществующий путь
        ui_image.file_path = str(tmp_path / "no_such_file.png")

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
