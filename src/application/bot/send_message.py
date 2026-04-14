from logging import Logger
from typing import Optional, TYPE_CHECKING, Union

from src.models.read_models import LogLevel
from src.exceptions.domain import StickerNotFound
from src.exceptions.telegram import TelegramBadRequestService
from src.infrastructure.files.file_system import FileStorage
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.models.update_models import UpdateUiImageDTO
from src.application.bot.sticker_sender import StickerSender
from src.application.models.systems import UiImagesService
from src.application.events.publish_event_handler import PublishEventHandler


if TYPE_CHECKING:
    from src.infrastructure.telegram.bot_client import TelegramClient
    from aiogram.types import (
        InlineKeyboardMarkup,
        ReplyKeyboardMarkup,
        ReplyKeyboardRemove,
        ForceReply,
        Message,
    )


class SendMessageService:

    def __init__(
        self,
        tg_client: "TelegramClient",
        path_builder: PathBuilder,
        ui_images_service: UiImagesService,
        limiter: RateLimiter,
        sticker_sender: StickerSender,
        file_system: FileStorage,
        publish_event: PublishEventHandler,
        logger: Logger,
    ):
        """
        :param limiter: ОБЯЗАТЕЛЬНОГО ГЛОБАЛЬНЫЙ!
        """
        self.tg_client = tg_client
        self.path_builder = path_builder
        self.ui_images_service = ui_images_service
        self.limiter = limiter
        self.sticker_sender = sticker_sender
        self.file_system = file_system
        self.publish_event = publish_event
        self.logger = logger

    async def send(
        self,
        chat_id: int,
        message: str = None,
        image_key: str = None,
        fallback_image_key: str = None,
        event_message_key: Optional[str] = None,
        reply_markup: Optional[Union[
            "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"
        ]] = None,
        parse_mode: Optional[str] = "HTML",
        always_show_photos: bool = False,
        message_effect_id: str = None,
        _retry_without_effect: bool = False,
    ) -> "Message":
        if not message and not (image_key or event_message_key):
            raise ValueError("Нужно указать message или (image_key или event_message_key)")

        await self._send_sticker_if_needed(chat_id, event_message_key)
        image_key = self._resolve_image_key(image_key, event_message_key)

        await self.limiter.acquire()

        if image_key:
            result = await self._send_with_image(
                chat_id=chat_id,
                message=message,
                image_key=image_key,
                fallback_image_key=fallback_image_key,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                always_show_photos=always_show_photos,
                message_effect_id=message_effect_id,
                retry=_retry_without_effect,
            )
            if result:
                return result

        return await self._send_text(
            chat_id, message, reply_markup, parse_mode, message_effect_id, _retry_without_effect
        )

    # -------------------- helpers --------------------

    async def _send_sticker_if_needed(self, chat_id: int, key: Optional[str]) -> None:
        if not key:
            return
        try:
            await self.sticker_sender.send(chat_id=chat_id, key=key)
        except StickerNotFound:
            pass

    def _resolve_image_key(self, image_key, event_message_key) -> str:
        return image_key or event_message_key

    async def _handle_effect_error(self, error, retry, message_effect_id, **kwargs) -> Optional["Message"]:
        if "EFFECT_ID_INVALID" in str(error) and message_effect_id and not retry:
            await self.publish_event.error_message_effect(message_effect_id)
            return await self.send(
                **kwargs,
                message_effect_id=None,
                _retry_without_effect=True,
            )
        return None

    async def _send_with_image(
        self,
        chat_id,
        message,
        image_key,
        fallback_image_key,
        reply_markup,
        parse_mode,
        always_show_photos,
        message_effect_id,
        retry,
    ) -> Optional["Message"]:
        ui_image = await self.ui_images_service.get_ui_image(image_key)

        if ui_image and (ui_image.show or always_show_photos):
            file_path = self.path_builder.build_path_ui_image(ui_image.file_name)

            try:
                if ui_image.file_id:
                    result = await self._send_with_file_id(
                        chat_id, ui_image, message, reply_markup, parse_mode, message_effect_id, retry
                    )
                    if result:
                        return result

                if self.file_system.exists(file_path):
                    return await self._send_with_file(
                        chat_id, ui_image, file_path, message, reply_markup, parse_mode, message_effect_id
                    )

                await self._handle_missing_image(image_key, ui_image.key)

            except TelegramBadRequestService as e:
                return await self._handle_effect_error(
                    e,
                    retry,
                    message_effect_id,
                    chat_id=chat_id,
                    message=message,
                    image_key=image_key,
                    fallback_image_key=fallback_image_key,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    always_show_photos=always_show_photos,
                )
            except Exception as e:
                self.logger.exception(f"Ошибка при отправке фото: {e}")

        elif fallback_image_key:
            return await self._send_with_image(
                chat_id,
                message,
                fallback_image_key,
                None,
                reply_markup,
                parse_mode,
                always_show_photos,
                message_effect_id,
                retry,
            )

        else:
            await self.publish_event.send_log(
                text=f"#Не_найдено_фото: {image_key}",
                log_lvl=LogLevel.WARNING,
            )

    async def _send_with_file_id(
        self, chat_id, ui_image, message, reply_markup, parse_mode, message_effect_id, retry
    ) -> Optional["Message"]:
        try:
            return await self.tg_client.send_photo(
                chat_id=chat_id,
                file_id=ui_image.file_id,
                caption=message,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                message_effect_id=message_effect_id,
            )
        except Exception as e:
            self.logger.warning(f"file_id невалиден: {ui_image.key}")
            return None

    async def _send_with_file(
        self, chat_id, ui_image, file_path, message, reply_markup, parse_mode, message_effect_id
    ) -> "Message":
        msg = await self.tg_client.send_photo(
            chat_id=chat_id,
            file_path=file_path,
            caption=message,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            message_effect_id=message_effect_id,
        )

        new_file_id = msg.photo[-1].file_id
        await self.ui_images_service.update_ui_image(
            key=ui_image.key,
            data=UpdateUiImageDTO(file_id=new_file_id),
            make_commit=True,
            filling_redis=True,
        )
        return msg

    async def _handle_missing_image(self, image_key, ui_key) -> None:
        self.logger.warning(f"#Не найдено фото: {image_key}")
        await self.publish_event.create_ui_image(ui_image_key=ui_key)

    async def _send_text(
        self,
        chat_id,
        message,
        reply_markup,
        parse_mode,
        message_effect_id,
        retry,
    ) -> Optional["Message"]:
        try:
            return await self.tg_client.send_message(
                chat_id,
                text=message or "None",
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                message_effect_id=message_effect_id,
            )
        except TelegramBadRequestService as e:
            return await self._handle_effect_error(
                e,
                retry,
                message_effect_id,
                chat_id=chat_id,
                message=message,
            )
        except Exception as e:
            self.logger.exception(f"Ошибка отправки сообщения: {e}")