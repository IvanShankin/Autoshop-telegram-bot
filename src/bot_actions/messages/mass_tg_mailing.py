import asyncio
import re
import html
from pathlib import Path
from typing import Optional, Tuple, AsyncGenerator

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramRetryAfter
from sqlalchemy import select

from src.bot_actions.bot_instance import get_bot
from src.exceptions.service_exceptions import TextTooLong, TextNotLinc
from src.services.database.core.database import get_db
from src.services.database.users.models import Users
from src.services.database.admins.models import SentMasMessages
from src.utils.core_logger import logger


SEMAPHORE_LIMIT = 15
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

MAX_CHARS_WITH_PHOTO = 1024
MAX_CHARS_WITHOUT_PHOTO = 4096

HTML_TAG_RE = re.compile(r"<[^>]+>")  # удаляет теги <...>


def visible_text_length(text: str) -> int:
    """
    Возвращает длину текста после удаления HTML-тегов и разворачивания HTML-entities.
    Теги (<b>, <code>, <i> и т.д.) не учитываются, а контент внутри них — учитывается.
    """
    if not isinstance(text, str):
        return 0
    # удаляем теги, оставляя содержимое
    without_tags = HTML_TAG_RE.sub("", text)
    # разворачиваем сущности типа &amp; &lt; и т.д.
    unescaped = html.unescape(without_tags)
    return len(unescaped)


async def validate_broadcast_inputs(
    bot: Bot,
    admin_chat_id: int,
    text: str,
    photo_path: Optional[str] = None,
    button_url: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[InlineKeyboardMarkup]]:
    """
    Проверяет входные данные и возвращает кортеж
    :return tuple: (text, photo_id_or_None, inline_kb_or_None)
    :except TextTooLong: текст слишком длинный
    :except TextNotLinc: текст в кнопке не является ссылкой
    :except FileNotFoundError: фото не найдено
    """
    if not isinstance(text, str) or not text.strip():
        raise TextTooLong("Text must be a non-empty string.")

    text = text.strip()
    visible_len = visible_text_length(text)

    if photo_path:
        max_len = MAX_CHARS_WITH_PHOTO
    else:
        max_len = MAX_CHARS_WITHOUT_PHOTO

    # для текста с фото своя длина
    if visible_len > max_len:
        raise TextTooLong(f"Message too long: {visible_len} chars (max {max_len}).")

    inline_kb = None
    if button_url:
        from urllib.parse import urlparse

        parsed = urlparse(button_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise TextNotLinc()

        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Open", url=button_url)]
        ])

    photo_id = await get_photo_identifier(bot, admin_chat_id, photo_path)

    return text, photo_id, inline_kb


async def get_photo_identifier(
    bot: Bot,
    admin_chat_id: int,
    photo_path: Optional[str] = None,
) -> str | None:
    """
    Если есть photo_path, то получит file_id и удалить сообщение у админа.
    :return str: file_id,
    :except FileNotFoundError: фото не найдено
    """
    if photo_path is None:
        return None

    path = Path(photo_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Фото не найдено: {photo_path}")

    # Заливаем временно админу, получить file_id и удалить сообщение
    sent_msg = await bot.send_photo(admin_chat_id, photo=FSInputFile(path), caption="(temp upload to get file_id)")
    file_id = sent_msg.photo[-1].file_id

    try:
        await bot.delete_message(admin_chat_id, sent_msg.message_id)
    except Exception:
        pass
    return file_id


async def _send_single(
    bot: Bot,
    user_id: int,
    text: str,
    photo_id: str,
    inline_kb: Optional[InlineKeyboardMarkup],
) -> Tuple[int, bool, Optional[Exception]]:
    """
    Пытается отправить одному пользователю.

    Использует глобальный semaphore.
    :return: Tuple(user_id, success, exception)
    """
    async with semaphore:
        try:
            if photo_id:
                await bot.send_photo(user_id, photo=photo_id, caption=text, reply_markup=inline_kb, parse_mode="HTML")
            else:
                await bot.send_message(user_id, text=text, reply_markup=inline_kb, parse_mode="HTML")
            return user_id, True, None

        except TelegramRetryAfter as e:
            return user_id, False, e

        except (TelegramForbiddenError, TelegramNotFound) as e:
            return user_id, False, e

        except Exception as e:
            logger.exception(f"Ошибка отправке пользователю: {user_id}")
            return user_id, False, e


async def broadcast_message_generator(
    text: str,
    admin_id: int,
    photo_path: Optional[str] = None,
    button_url: Optional[str] = None,
    concurrency: int = SEMAPHORE_LIMIT,
) -> AsyncGenerator[Tuple[int, bool, Optional[Exception]], None]:
    """
    Асинхронный генератор, который после отправки сообщения возвращает кортеж:
    :return: AsyncGenerator[Tuple(user_id, success: bool, error_or_none)]
    """
    # обновим semaphore по concurrency
    global semaphore
    semaphore = asyncio.Semaphore(concurrency)

    bot = await get_bot()

    text, photo_id, inline_kb = await validate_broadcast_inputs(bot, admin_id, text, photo_path, button_url)

    # получаем user_ids стримом и запускаем пул задач
    async def gen_user_ids():
        async with get_db() as session:
            result = await session.stream_scalars(select(Users.user_id))
            async for uid in result:
                yield uid

    tasks = set()
    success = 0
    failed = 0
    batch_size = max(1, concurrency * 2)  # сколько тасков держать в пуле (безопасно немного больше concurrency)

    async for uid in gen_user_ids():
        task = asyncio.create_task(_send_single(bot, uid, text, photo_id, inline_kb))
        tasks.add(task)

        # если пул большой — дожидаемся хотя бы одного завершения
        if len(tasks) >= batch_size:
            done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for d in done:
                uid_res, ok, exc = d.result()
                if ok:
                    success += 1
                else:
                    failed += 1
                yield uid_res, ok, exc

    # дождаться оставшихся
    if tasks:
        done, _ = await asyncio.wait(tasks)
        for d in done:
            uid_res, ok, exc = d.result()
            if ok:
                success += 1
            else:
                failed += 1
            yield uid_res, ok, exc


    async with get_db() as session:
        session.add(SentMasMessages(
            content=text,
            user_id=admin_id,
            photo_path=photo_path,
            button_url=button_url,
            number_received=success,
            number_sent=failed + success
        ))
        await session.commit()

    logger.info(f"Рассылка закончена, успешных {success} из {failed + success}")
