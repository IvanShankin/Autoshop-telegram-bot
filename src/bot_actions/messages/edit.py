import os.path

from typing import Optional, Any
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from pydantic import ValidationError
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply, FSInputFile, \
    InputMediaPhoto

from src.bot_actions.bot_instance import get_bot
from src.bot_actions.messages import send_log, send_message
from src.services.database.system.actions import get_ui_image, update_ui_image
from src.services.filesystem.actions import check_file_exists
from src.services.filesystem.media_paths import create_path_ui_image
from src.utils.core_logger import get_logger


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


async def _try_edit_media_by_file_id(
        bot: Bot,
        chat_id: int,
        message_id: int,
        file_id: str,
        caption: str,
        reply_markup,
        parse_mode: Optional[str] = "HTML"
) -> bool:
    """Пробуем заменить media по существующему file_id. Возвращаем True при успехе."""
    try:
        media = InputMediaPhoto(media=file_id, caption=caption, parse_mode=parse_mode)
        await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
        return True
    except ValidationError: # если текс не передан
        return False
    except TelegramForbiddenError as e:
        logger = get_logger(__name__)
        logger.warning(f"[edit_message] Forbidden editing media by file_id chat={chat_id} id={message_id}: {e}")
        return False
    except TelegramBadRequest as e:
        # это не критичные ошибки
        if 'canceled by new editMessageMedia request' in e.message or 'message is not modified' in e.message:
            return True # это сообщение уже обработано или не надо обрабатывать
        elif _is_file_id_invalid_error(e):
            logger = get_logger(__name__)
            logger.info(f"[edit_message] file_id invalid for file_id={file_id}; will try upload. Detail: {e}")
        elif _is_message_not_found_error(e):
            logger = get_logger(__name__)
            logger.info(f"[edit_message] message not found when editing media by file_id chat={chat_id} id={message_id}")
        else:
            logger = get_logger(__name__)
            logger.exception(f"[edit_message] TelegramBadRequest editing by file_id: {e}")
        return False
    except Exception as e:
        logger = get_logger(__name__)
        logger.exception(f"[edit_message] Unexpected error editing media by file_id: {e}")
        return False


async def _try_edit_media_by_file(
        bot: Any,
        chat_id: int,
        message_id: int,
        ui_image,
        caption: str,
        reply_markup,
        parse_mode: Optional[str] = "HTML",
        fallback_image_key:  Optional[str] = None,
    ) -> bool:
    """Пробуем заменить media, загрузив файл с диска. При успехе сохраняем новый file_id (если есть)."""
    logger = get_logger(__name__)
    file_path = create_path_ui_image(file_name=ui_image.file_name)
    try:
        photo = FSInputFile(file_path)
    except (FileNotFoundError, AttributeError):
        logger.warning(f"[edit_message] Local file not found: {file_path}")
        if fallback_image_key:
            ui_image = await get_ui_image(fallback_image_key)

            if ui_image:
                file_path = create_path_ui_image(file_name=ui_image.file_name)
                if ui_image.file_id:
                    ok = await _try_edit_media_by_file_id(bot, chat_id, message_id, ui_image.file_id, caption, reply_markup)
                    if ok:
                        return True # успешно

                if not os.path.isfile(file_path):
                    await send_log(f"#Не_найдено_фото [edit_message]. \nget_ui_image='{ui_image.key}'")  # лучше после отправки пользователю
                else:
                    ok = await _try_edit_media_by_file(bot, chat_id, message_id, ui_image, caption, reply_markup)
                    if ok:
                        return True # успешно

        return False

    try:
        media = InputMediaPhoto(media=photo, caption=caption, parse_mode=parse_mode)
        msg = await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=reply_markup)
        # извлекаем новый file_id если он есть
        try:
            if hasattr(msg, "photo") and msg.photo:
                new_file_id = msg.photo[-1].file_id
                if new_file_id:
                    await update_ui_image(key=ui_image.key, show=ui_image.show, file_id=new_file_id)
        except TelegramBadRequest as e:
            # это не критичные ошибки
            if 'canceled by new editMessageMedia request' in e.message or 'message is not modified' in e.message:
                return True # это сообщение уже обработано или не надо обрабатывать
            else:
                logger.exception("[edit_message] Failed to extract/save new file_id after edit_message_media")
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


async def _try_edit_text(
        bot: Bot,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup,
        parse_mode: Optional[str] = "HTML"
) -> Optional[bool]:
    """
    Пробуем отредактировать текст. Возвращает:
      - True  => успешно отредактировали
      - False => редактирование не удалось (например message not found)
      - None  => сообщение не изменилось (message is not modified) — это не ошибка, но менять не нужно
    """
    logger = get_logger(__name__)
    try:
        if not text:
            text = "None"

        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode=parse_mode,
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
    message: str = None,
    image_key: Optional[str] = None,
    fallback_image_key:  Optional[str] = None,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    parse_mode: Optional[str] = "HTML",
    always_show_photos: bool = False
):
    """
    Попытаться отредактировать сообщение. Если редактирование невозможно — отправить новое (через send_message).
    :param always_show_photos: Будет показывать фото даже если стоит флаг Show == False
    """
    bot = await get_bot()
    logger = get_logger(__name__)

    # Если есть image_key — пробуем редактировать/заменить media
    if image_key:
        ui_image = await get_ui_image(image_key)

        if ui_image and (ui_image.show or always_show_photos):
            file_path = create_path_ui_image(file_name=ui_image.file_name)
            # сначала file_id
            if ui_image.file_id:
                ok = await _try_edit_media_by_file_id(bot, chat_id, message_id, ui_image.file_id, message, reply_markup, parse_mode)
                if ok:
                    return  # успешно
                # пробуем редактировать media с загрузкой файла
                ok = await _try_edit_media_by_file(bot, chat_id, message_id, ui_image, message, reply_markup, parse_mode)
                if ok:
                    return  # успешно
                # не удалось отредактировать — пробуем удалить старое и отправить новое
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    logger.info(f"[edit_message] Deleted old message with media chat={chat_id} id={message_id}")
                except Exception as e:
                    logger.warning(f"[edit_message] Failed to delete old message before resend: {e}")

                await send_message(
                    chat_id=chat_id,
                    message=message,
                    image_key=image_key,
                    fallback_image_key=fallback_image_key,
                    reply_markup=reply_markup
                )
                return
            elif check_file_exists(file_path):
                # пробуем редактировать media с загрузкой файла
                ok = await _try_edit_media_by_file(bot, chat_id, message_id, ui_image, message, reply_markup, parse_mode)
                if ok:
                    return  # успешно
                # не удалось отредактировать — пробуем удалить старое и отправить новое
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    logger.info(f"[edit_message] Deleted old message with media chat={chat_id} id={message_id}")
                except Exception as e:
                    logger.warning(f"[edit_message] Failed to delete old message before resend: {e}")

                await send_message(
                    chat_id=chat_id,
                    message=message,
                    image_key=image_key,
                    fallback_image_key=fallback_image_key,
                    reply_markup=reply_markup
                )
                return
            else:
                text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{image_key}'"
                logger.warning(text)
                await send_log(text)

                # если не нашли ui_image или не надо отсылать его (not ui_image.show)
        elif (not ui_image or ui_image and not ui_image.show) and fallback_image_key:
            text = ''
            if not ui_image:
                text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{image_key}'"
                logger.warning(text)

            # если не нашли ui_image или не надо отсылать его
            ui_image = await get_ui_image(fallback_image_key)

            if ui_image:
                file_path = create_path_ui_image(file_name=ui_image.file_name)
                if ui_image.file_id:
                    ok = await _try_edit_media_by_file_id(bot, chat_id, message_id, ui_image.file_id, message, reply_markup, parse_mode)
                    if ok:
                        if not ui_image:
                            await send_log(text)
                        return  # успешно
                elif check_file_exists(file_path):
                    # пробуем редактировать media с загрузкой файла
                    ok = await _try_edit_media_by_file(bot, chat_id, message_id, ui_image, message, reply_markup, parse_mode)
                    if ok:
                        if not ui_image:
                            await send_log(text)
                        return  # успешно
                else:
                    text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{fallback_image_key}'"
                    logger.warning(text)
                    await send_log(text)

            else:
                await send_log(text)
        elif not ui_image:
            # если нет замены для фото
            text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{image_key}'"
            logger.warning(text)
            await send_log(text)

        # если ui_image не найден или скрыт (show=False), то переходим к ветке "без фото"

    # --- Новое сообщение без фото ---
    # если старое было с фото — нужно удалить и отправить новое, т.к. нельзя удалить фото редактированием
    # попробуем сначала отредактировать текст; если ошибка "there is no text in the message to edit" → значит было фото
    text_result = await _try_edit_text(bot, chat_id, message_id, message, reply_markup, parse_mode)

    if text_result is True or text_result is None:
        return  # успешно отредактировали текст

    # не удалось отредактировать текст — удаляем и отправляем новое
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"[edit_message] Deleted old message before sending new one chat={chat_id} id={message_id}")
    except Exception as e:
        logger.warning(f"[edit_message] Failed to delete old message before sending new one: {e}")

    await send_message(
        chat_id=chat_id,
        message=message,
        image_key=image_key,
        fallback_image_key=fallback_image_key,
        reply_markup=reply_markup,
        parse_mode=parse_mode
    )
    return
