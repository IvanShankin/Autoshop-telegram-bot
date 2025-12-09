from types import SimpleNamespace
import pytest


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

        from src.bot_actions.messages import edit as modul_1
        from src.bot_actions.messages import send as modul_2
        monkeypatch.setattr(modul_1, "update_ui_image", fake_update_ui_image)
        monkeypatch.setattr(modul_2, "update_ui_image", fake_update_ui_image)

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

        assert len(fake_bot.sent) == 1
        chat_id, text, kwargs = fake_bot.sent[0]
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

