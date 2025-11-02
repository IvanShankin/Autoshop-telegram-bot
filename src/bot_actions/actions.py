from typing import Optional, Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from src.bot_actions.bot_instance import get_bot_logger
from src.config import MAIN_ADMIN
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply, FSInputFile, \
    InputMediaPhoto

from src.bot_actions.bot_instance import get_bot
from src.services.database.system.actions import get_ui_image, update_ui_image
from src.services.database.system.actions import get_settings
from src.utils.core_logger import logger


def _is_message_not_found_error(exc: Exception) -> bool:
    text = str(exc).lower()
    phrases = [
        "message to edit not found",
        "message not found",
        "chat not found",
        "message can't be edited",
        "message identifier is not specified",
        "message_id is invalid",
    ]
    return any(p in text for p in phrases)


def _is_message_not_modified_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "message is not modified" in text or "message text is not modified" in text

def _is_minor_errors(exc: Exception) -> bool:
    text = str(exc).lower()
    phrases = [
        # если пытаемся отредактировать сообщение с фото на сообщение без фото (такие только удалять)
        "there is no text in the message to edit",
    ]
    return any(p in text for p in phrases)

def _is_file_id_invalid_error(exc: Exception) -> bool:
    """Определяет, что file_id недействителен / не найден на сервере Telegram."""
    text = str(exc).lower()
    # Telegram/aiogram часто возвращают похожие формулировки, поэтому ищем ключевые слова
    phrases = [
        "file not found",
        "file_id not found",
        "bad request: file",
        "wrong file_id",
        "file is empty",
    ]
    return any(p in text for p in phrases)


async def _try_edit_media_by_file_id(bot: Bot, chat_id: int, message_id: int, file_id: str,
                                     caption: str, reply_markup) -> bool:
    """Пробуем заменить media по существующему file_id. Возвращаем True при успехе."""
    try:
        media = InputMediaPhoto(media=file_id, caption=caption, parse_mode="HTML")
        await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
        return True
    except TelegramForbiddenError as e:
        logger.warning(f"[edit_message] Forbidden editing media by file_id chat={chat_id} id={message_id}: {e}")
        return False
    except TelegramBadRequest as e:
        if _is_file_id_invalid_error(e):
            logger.info(f"[edit_message] file_id invalid for file_id={file_id}; will try upload. Detail: {e}")
        elif _is_message_not_found_error(e):
            logger.info(f"[edit_message] message not found when editing media by file_id chat={chat_id} id={message_id}")
        else:
            logger.exception(f"[edit_message] TelegramBadRequest editing by file_id: {e}")
        return False
    except Exception as e:
        logger.exception(f"[edit_message] Unexpected error editing media by file_id: {e}")
        return False


async def _try_edit_media_by_file(bot: Any, chat_id: int, message_id: int, ui_image, caption: str, reply_markup) -> bool:
    """Пробуем заменить media, загрузив файл с диска. При успехе сохраняем новый file_id (если есть)."""
    try:
        photo = FSInputFile(ui_image.file_path)
    except FileNotFoundError:
        logger.warning(f"[edit_message] Local file not found: {ui_image.file_path}")
        return False
    try:
        media = InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML")
        msg = await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
        # извлекаем новый file_id если он есть
        try:
            if hasattr(msg, "photo") and msg.photo:
                new_file_id = msg.photo[-1].file_id
                if new_file_id:
                    await update_ui_image(key=ui_image.key, show=ui_image.show, file_id=new_file_id)
        except Exception:
            logger.exception("[edit_message] Failed to extract/save new file_id after edit_message_media")
        return True
    except TelegramBadRequest as e:
        if _is_message_not_found_error(e):
            logger.info(f"[edit_message] edit_message_media (upload) message not found, chat={chat_id} id={message_id}")
        else:
            logger.exception(f"[edit_message] edit_message_media (upload) failed: {e}")
        return False
    except TelegramForbiddenError as e:
        logger.warning(f"[edit_message] Forbidden editing media (upload): {e}")
        return False
    except Exception as e:
        logger.exception(f"[edit_message] Unexpected error editing media (upload): {e}")
        return False


async def _try_edit_text(bot: Bot, chat_id: int, message_id: int, text: str, reply_markup) -> Optional[bool]:
    """
    Пробуем отредактировать текст. Возвращает:
      - True  => успешно отредактировали
      - False => редактирование не удалось (например message not found)
      - None  => сообщение не изменилось (message is not modified) — это не ошибка, но менять не нужно
    """
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        return True

    except TelegramBadRequest as e:
        if _is_message_not_modified_error(e):
            logger.debug(f"[edit_message] Message not modified chat={chat_id} id={message_id}")
            return None
        if _is_message_not_found_error(e):
            logger.info(f"[edit_message] edit_message_text: message not found chat={chat_id} id={message_id}")
            return False
        if _is_minor_errors(e):
            return False

        logger.exception(f"[edit_message] TelegramBadRequest editing text: {e}")
        return False

    except TelegramForbiddenError as e:
        logger.warning(f"[edit_message] Forbidden editing text chat={chat_id} id={message_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"[edit_message] Unexpected error edit_message_text: {e}")
        return False

async def edit_message(
    chat_id: int,
    message_id: int,
    message: str,
    image_key: Optional[str] = None,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None
):
    """
    Попытаться отредактировать сообщение. Если редактирование невозможно — отправить новое (через send_message).
    Логика разделена на небольшие функции для читаемости и тестируемости.
    """
    bot = await get_bot()

    # Если есть image_key — пробуем редактировать/заменить media
    if image_key:
        ui_image = await get_ui_image(image_key)
        if ui_image and ui_image.show:
            # сначала file_id
            if ui_image.file_id:
                ok = await _try_edit_media_by_file_id(bot, chat_id, message_id, ui_image.file_id, message, reply_markup)
                if ok:
                    return  # успешно

            # пробуем редактировать media с загрузкой файла
            ok = await _try_edit_media_by_file(bot, chat_id, message_id, ui_image, message, reply_markup)
            if ok:
                return  # успешно
            # не удалось отредактировать — пробуем удалить старое и отправить новое
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"[edit_message] Deleted old message with media chat={chat_id} id={message_id}")
            except Exception as e:
                logger.warning(f"[edit_message] Failed to delete old message before resend: {e}")

            await send_message(chat_id=chat_id, message=message, image_key=image_key, reply_markup=reply_markup)
            return

        # если ui_image не найден или скрыт (show=False), то переходим к ветке "без фото"

    # --- Новое сообщение без фото ---
    # если старое было с фото — нужно удалить и отправить новое, т.к. нельзя удалить фото редактированием
    # попробуем сначала отредактировать текст; если ошибка "there is no text in the message to edit" → значит было фото
    text_result = await _try_edit_text(bot, chat_id, message_id, message, reply_markup)

    if text_result is True or text_result is None:
        return  # ✅ успешно отредактировали текст

    # не удалось отредактировать текст — удаляем и отправляем новое
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"[edit_message] Deleted old message before sending new one chat={chat_id} id={message_id}")
    except Exception as e:
        logger.warning(f"[edit_message] Failed to delete old message before sending new one: {e}")

    await send_message(chat_id=chat_id, message=message, image_key=None, reply_markup=reply_markup)
    return

async def send_message(
        chat_id: int,
        message: str = None,
        image_key: str = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None
):
    """
    Отправит сообщение по-указанному chat_id, если есть image_key, то отправит фото с сообщением.

    В обоих случаях parse_mode="HTML"
    """
    if not message and not image_key:
        raise ValueError("При отсылке нового сообщения необходимо указать хотя бы 'message' или 'image_key'")

    bot = await get_bot()
    if image_key:
        ui_image = await get_ui_image(image_key)
        if ui_image and ui_image.show: # если есть изображение по данному пути и его можно показывать
            try:
                # Если уже есть file_id — отправляем без загрузки
                if ui_image.file_id:
                    try:
                        await bot.send_photo(
                            chat_id=chat_id,
                            photo=ui_image.file_id,
                            caption=message,
                            parse_mode="HTML",
                            reply_markup=reply_markup
                        )
                        return
                    except Exception as e:
                        # file_id устарел или недействителен
                        if "file" in str(e).lower() or "not found" in str(e).lower():
                            logger.warning(f"[send_message] file_id недействителен для {ui_image.key}, переотправляем файл.")

                # Иначе — отправляем файл с диска
                photo = FSInputFile(ui_image.file_path)
                msg = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=message,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )

                # Сохраняем file_id для будущего использования
                new_file_id = msg.photo[-1].file_id
                await update_ui_image(key=ui_image.key, show=ui_image.show, file_id=new_file_id)

                return

            except Exception as e:
                logger.exception(f"#Ошибка при отправке фото: {str(e)}")
        else:
            text = f"#Не_найдено_фото. \nget_ui_image='{image_key}'"
            logger.warning(text)

            ui_image = await get_ui_image('default')
            photo = FSInputFile(ui_image.file_path)
            msg = await bot.send_photo(chat_id, photo=photo, caption=message, parse_mode="HTML", reply_markup=reply_markup)

            await send_log(text) # лучше после отправки пользователю

            # Сохраняем file_id для будущего использования
            new_file_id = msg.photo[-1].file_id
            await update_ui_image(key=ui_image.key, show=ui_image.show, file_id=new_file_id)
    try:
        if message:
            await bot.send_message(chat_id, text=message, parse_mode="HTML", reply_markup=reply_markup)
    except Exception as e:
        logger.exception(f"#Ошибка при отправке сообщения. Ошибка: {str(e)}")

async def send_log(text: str, channel_for_logging_id: int = None):
    """
    :param text: Длинна должна быть в пределах 1 - 4096 символов
    :param channel_for_logging_id: если не передавать то возьмёт сам из настроек
    """

    # формируем сообщения разбивая по максимальной длине (4096)
    parts = []
    for i in range(0, len(text), 4096):
        parts.append(text[i:i + 4096])


    if not channel_for_logging_id:
        settings = await get_settings()
        channel_for_logging_id = settings.channel_for_logging_id

    bot = await get_bot_logger()

    try:
        for message in parts:
            await bot.send_message(channel_for_logging_id, message)
    except Exception as e:
        settings = await get_settings()
        message_error = f"Не удалось отправить сообщение в канал с логами. \n\nОшибка: {str(e)}"
        logger.error(message_error)

        try:
            if settings.support_username:
                await bot.send_message(
                    settings.support_username,
                    f'Не удалось отправить лог в канал!\nID используемого канала: {channel_for_logging_id} '
                    f'\n\nСообщение:'
                )
                for message in parts:
                    await bot.send_message(settings.support_username,message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения support. Ошибка: {str(e)}")

        try:
            await bot.send_message(
                MAIN_ADMIN,
                f'Не удалось отправить лог в канал!\nID используемого канала: {channel_for_logging_id} '
                f'\n\nСообщение:\n{message_error}'
            )
            for message in parts:
                await bot.send_message(MAIN_ADMIN, message)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения MAIN_ADMIN. Ошибка: {str(e)}")
