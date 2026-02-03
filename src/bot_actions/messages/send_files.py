import os
from pathlib import Path
from typing import Optional

import mimetypes

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import (
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
    Message,
    FSInputFile,
)

from src.bot_actions.bot_instance import get_bot
from src.config import get_global_rate_limit, get_config
from src.services.database.system.actions import get_file, update_file
from src.utils.core_logger import get_logger


_PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}
_ANIMATION_EXT = {".gif", ".webp"}


def _guess_media_kind_from_path(path: Path) -> str:
    """
    Возвращает один из: "photo", "video", "animation", "document"
    """
    suffix = path.suffix.lower()
    if suffix in _PHOTO_EXT:
        return "photo"
    if suffix in _VIDEO_EXT:
        return "video"
    if suffix in _ANIMATION_EXT:
        # gif -> animation; webp may be either but treat as animation
        return "animation"

    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        if mime.startswith("image/"):
            return "photo"
        if mime.startswith("video/"):
            return "video"
        if mime.startswith("audio/"):
            return "document"
    return "document"


async def send_document(
    chat_id: int,
    file_id: Optional[str] = None,
    file_path: Optional[str] = None,
    message: Optional[str] = None,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    parse_mode: Optional[str] = "HTML",
    type_based: bool = True
) -> Optional[Message]:
    """
    Отправляет файл/медиа в чат.
    Если type_based == True и извест путь (file_path) — выберет метод в зависимости от расширения (photo/video/animation/document).
    В первую очередь пробует отправить через file_id (если задан). При ошибке попробует через file_path (если задан).

    :param type_based: Отошлёт файл в зависимости от его типа. Если у него расширение фото, то отошлёт как фото и т.д.
    :return: Возвращает aiogram.types.Message или None (если отправить не удалось).
    """
    logger = get_logger(__name__)
    bot = await get_bot()

    if file_id is None and file_path is None:
        raise ValueError("Необходимо указать хотя бы одно из двух: 'file_id' или 'file_path' ")

    if message and len(message) > 1024:
        raise ValueError("Достигнут лимит сообщения с фото/документом в 1024 символа")

    # Определим желаемый тип отправки (если возможно)
    media_kind = None
    if type_based and file_path:
        media_kind = _guess_media_kind_from_path(Path(file_path))

    # Функции отправки — в порядке пробования
    async def _send_via_file_id(kind: Optional[str]) -> Optional[Message]:
        """Попытка отправить через file_id. kind может быть None -> используем document."""
        try:
            if kind == "photo":
                return await bot.send_photo(chat_id, file_id, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)
            if kind == "video":
                return await bot.send_video(chat_id, file_id, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)
            if kind == "animation":
                return await bot.send_animation(chat_id, file_id, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)
            # fallback: document
            return await bot.send_document(chat_id, file_id, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)
        except TelegramAPIError as e:
            logger.warning("send via file_id failed: %s", e)
            return None
        except Exception as e:
            logger.exception("Unexpected error while sending via file_id: %s", e)
            return None

    async def _send_via_path(kind: Optional[str]) -> Optional[Message]:
        """Попытка отправить через локальный путь."""
        if not file_path:
            return None
        p = Path(file_path)
        if not p.exists():
            logger.warning("file_path not exists: %s", file_path)
            return None

        input_file = FSInputFile(str(p))

        try:
            if kind == "photo":
                return await bot.send_photo(chat_id, input_file, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)
            if kind == "video":
                return await bot.send_video(chat_id, input_file, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)
            if kind == "animation":
                return await bot.send_animation(chat_id, input_file, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)

            # fallback
            return await bot.send_document(chat_id, input_file, caption=message or "", parse_mode=parse_mode, reply_markup=reply_markup)
        except TelegramAPIError as e:
            logger.warning("send via file_path failed: %s", e)
            return None
        except Exception as e:
            logger.exception("Unexpected error while sending via file_path: %s", e)
            return None

    await get_global_rate_limit().acquire()

    if file_id:
        # Если type_based и мы знаем media_kind — пробуем сразу с тем типом
        if type_based and media_kind:
            msg = await _send_via_file_id(media_kind)
            if msg:
                return msg
            # fallback: пробуем как документ
            msg = await _send_via_file_id("document")
            if msg:
                return msg
        else:
            # либо type_based=False, либо не знаем media_kind -> сначала как документ,
            # можно попробовать и как photo, но документ безопаснее
            msg = await _send_via_file_id("document")
            if msg:
                return msg
            # пробуем как фото (fallback)
            msg = await _send_via_file_id("photo")
            if msg:
                return msg

    # если file_id не дали или попытки неудачны
    if file_path:
        # если media_kind известен — используем его
        if type_based and media_kind:
            msg = await _send_via_path(media_kind)
            if msg:
                return msg
            # fallback -> document
            msg = await _send_via_path("document")
            if msg:
                return msg
        else:
            # просто документ
            msg = await _send_via_path("document")
            if msg:
                return msg

    # ноль попыток дал результат
    logger.error("Failed to send file to chat %s (file_id=%s, file_path=%s)", chat_id, file_id, file_path)
    return None


async def send_file_by_file_key(
    chat_id: int,
    file_key: str,
    message: Optional[str] = None,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    parse_mode: Optional[str] = "HTML",
    type_based: Optional[bool] = False,
    one_attempt: bool = False
):
    """
    Отошлёт файл по указанному `chat_id`
    :param file_key:
    :param type_based: Отошлёт файл в зависимости от его типа. Если у него расширение фото, то отошлёт как фото и т.д.
    :param one_attempt: Флаг попытаться отправить только раз.
    :except FileNotFoundError: Если на диске не нашёлся файл
    :except ValueError: Если такого ключа нет в БД
    """
    bot = await get_bot()
    conf = get_config()

    file = await get_file(file_key)
    if not file:
        raise ValueError(f"Файл по ключу: '{file_key}' не найден")

    if file.file_tg_id:
        document = file.file_tg_id
    else:
        full_file_path = conf.paths.files_dir / Path(file.file_path)
        if not os.path.isfile(full_file_path):
            raise FileNotFoundError()

        document = FSInputFile(full_file_path)

    await get_global_rate_limit().acquire()
    try:
        message = await bot.send_document(
            chat_id=chat_id,
            document=document,
            caption=message,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    except TelegramBadRequest as e:
        logger = get_logger(__name__)
        logger.warning(f"При попытки отослать документ произошла ошибка: {str(e)}")
        # может быть из-за плохого file_tg_id
        await update_file(file_key, file_tg_id=None)
        if not one_attempt and file.file_tg_id:
            await send_file_by_file_key(
                chat_id=chat_id,
                file_key=file_key,
                message=message,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                type_based=type_based,
                one_attempt=True
            )
        return

    await update_file(file_key, file_tg_id=message.document.file_id)
