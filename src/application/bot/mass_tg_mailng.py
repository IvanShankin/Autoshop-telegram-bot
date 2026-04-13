import asyncio
import html
import re
import validators

from logging import Logger
from typing import Optional, Tuple, AsyncGenerator, TYPE_CHECKING

from src.config import Config
from src.exceptions import TextTooLong, TextNotLinc
from src.exceptions.telegram import TelegramRetryAfterService, TelegramForbiddenErrorService, TelegramNotFoundService
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.models.create_models.admins import CreateSentMassMessages
from src.models.telegram import InlineKeyboardMarkupService, InlineKeyboardButtonService
from src.repository.database.users import UsersRepository
from src.infrastructure.files.file_system import copy_file
from src.application.models.admins import SentMassMessagesService


if TYPE_CHECKING:
    from src.infrastructure.telegram.bot_client import TelegramClient
    from aiogram.types import InlineKeyboardMarkup


MAX_CHARS_WITH_PHOTO = 1024
MAX_CHARS_WITHOUT_PHOTO = 4096

HTML_TAG_RE = re.compile(r"<[^>]+>")  # удаляет теги <...>


class MassTgMailingService:

    def __init__(
        self,
        tg_client: "TelegramClient",
        limiter: RateLimiter,
        users_repo: UsersRepository,
        sent_mass_msg_service: SentMassMessagesService,
        conf: Config,
        logger: Logger,
    ):
        self.tg_client = tg_client
        self.limiter = limiter
        self.users_repo = users_repo
        self.sent_mass_msg_service = sent_mass_msg_service
        self.conf = conf
        self.logger = logger


    def visible_text_length(self, text: str) -> int:
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


    async def _validate_broadcast_inputs(
        self,
        admin_chat_id: int,
        text: str,
        show_image: bool,
        photo_path: Optional[str] = None,
        button_url: Optional[str] = None,
    ) -> Tuple[str, Optional[str],  Optional[str], Optional["InlineKeyboardMarkup"]]:
        """
        Проверяет входные данные и возвращает кортеж
        :return: Tuple (text, photo_id_or_None, new_photo_path_or_None, inline_kb_or_None)
        :except TextTooLong: текст слишком длинный
        :except TextNotLinc: текст в кнопке не является ссылкой
        :except FileNotFoundError: фото не найдено
        """
        if not isinstance(text, str) or not text.strip():
            raise TextTooLong("Text must be a non-empty string.")

        text = text.strip()
        visible_len = self.visible_text_length(text)

        if photo_path and show_image:
            max_len = MAX_CHARS_WITH_PHOTO
        else:
            max_len = MAX_CHARS_WITHOUT_PHOTO

        # для текста с фото своя длина
        if visible_len > max_len:
            raise TextTooLong(f"Message too long: {visible_len} chars (max {max_len}).")

        inline_kb = None
        if button_url:
            if not validators.url(button_url):
                raise TextNotLinc()

            await self.tg_client.get_inline_keyboard_markup()
            inline_kb = InlineKeyboardMarkupService(inline_keyboard=[
                [InlineKeyboardButtonService(text="Open", url=button_url)]
            ])

        photo_id = None
        new_file_path = None

        if photo_path and show_image:
            photo_id, new_file_path = await self._get_photo_identifier(admin_chat_id, photo_path)

        return text, photo_id, new_file_path, inline_kb

    async def _get_photo_identifier(
        self,
        admin_chat_id: int,
        photo_path: Optional[str] = None,
    ) -> Tuple[str | None, str | None] | None :
        """
        Если есть photo_path, то получит file_id и удалить сообщение у админа.
        :return: Tuple (file_id, new_image_path)
        :except FileNotFoundError: фото не найдено
        """
        if photo_path is None:
            return None, None

        new_file_path = copy_file(src=photo_path, dst_dir=self.conf.paths.sent_mass_msg_image_dir)

        # Заливаем временно админу, получить file_id и удалить сообщение
        sent_msg = await self.tg_client.send_photo(admin_chat_id, file_path=new_file_path, caption="(temp upload to get file_id)")
        file_id = sent_msg.photo[-1].file_id

        try:
            await self.tg_client.delete_message(admin_chat_id, sent_msg.message_id)
        except Exception:
            pass
        return file_id, new_file_path

    async def _send_single(
        self,
        user_id: int,
        text: str,
        file_id: str,
        inline_kb: Optional["InlineKeyboardMarkup"],
    ) -> Tuple[int, bool, Optional[Exception]]:
        """
        Пытается отправить одному пользователю.

        Использует глобальный semaphore.
        :return: Tuple(user_id, success, exception)
        """

        async with self.conf.different.semaphore_mailing_limit:
            await self.limiter.acquire()

            try:
                if file_id:
                    await self.tg_client.send_photo(user_id, file_id=file_id, caption=text, reply_markup=inline_kb, parse_mode="HTML")
                else:
                    await self.tg_client.send_message(user_id, text=text, reply_markup=inline_kb, parse_mode="HTML")
                return user_id, True, None

            except TelegramRetryAfterService as e:
                return user_id, False, e

            except (TelegramForbiddenErrorService, TelegramNotFoundService) as e:
                return user_id, False, e

            except Exception as e:
                self.logger.exception(f"Ошибка отправке пользователю: {user_id}")
                return user_id, False, e


    async def broadcast_message_generator(
        self,
        text: str,
        admin_id: int,
        show_image: bool = False,
        photo_path: Optional[str] = None,
        button_url: Optional[str] = None,
    ) -> AsyncGenerator[Tuple[int, bool, Optional[Exception]], None]:
        """
        Асинхронный генератор, который после отправки сообщения возвращает кортеж

        Файл копируется на сервер и новый путь присваивается в SentMasMessages,
        что бы в дальнейшем админ не мог изменить фото

        :return: AsyncGenerator[Tuple(user_id, success: bool, error_or_none)]

        :except TextTooLong: текст слишком длинный
        :except TextNotLinc: текст в кнопке не является ссылкой
        :except FileNotFoundError: фото не найдено
        """

        text, file_id, new_photo_path, inline_kb = await self._validate_broadcast_inputs(
            admin_chat_id=admin_id,
            text=text,
            show_image=show_image,
            photo_path=photo_path,
            button_url=button_url
        )

        tasks = set()
        success = 0
        failed = 0
        batch_size = max(1, self.conf.different.semaphore_mailing_limit * 2)  # сколько тасков держать в пуле (безопасно немного больше concurrency)

        async for uid in self.users_repo.gen_user_ids():
            task = asyncio.create_task(self._send_single(uid, text, file_id, inline_kb))
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


        await self.sent_mass_msg_service.create_msg(
            user_id=admin_id,
            data=CreateSentMassMessages(
                content=text,
                photo_path=new_photo_path,
                photo_id=file_id,
                button_url=button_url,
                number_received=success,
                number_sent=failed + success
            ),
            make_commit=True
        )

        self.logger.info(f"Рассылка закончена, успешных {success} из {failed + success}")
