from logging import Logger
from typing import Optional, TYPE_CHECKING, Union
from pydantic import ValidationError

from src.models.read_models import LogLevel
from src.exceptions.domain import StickerNotFound
from src.exceptions.telegram import TelegramBadRequestService, TelegramForbiddenErrorService
from src.infrastructure.files.file_system import FileStorage
from src.infrastructure.files.path_builder import PathBuilder
from src.infrastructure.telegram.rate_limit import RateLimiter
from src.models.update_models import UpdateUiImageDTO
from src.models.update_models.bot_actions import EditMessagePhoto
from src.services.bot.send_message import SendMessageService
from src.services.bot.sticker_sender import StickerSender
from src.services.models.systems import UiImagesService
from src.services.events.publish_event_handler import PublishEventHandler


if TYPE_CHECKING:
    from src.infrastructure.telegram.client import TelegramClient
    from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply


class EditMessageService:

    def __init__(
        self,
        tg_client: "TelegramClient",
        send_msg_service: SendMessageService,
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
        self.send_msg_service = send_msg_service
        self.path_builder = path_builder
        self.ui_images_service = ui_images_service
        self.limiter = limiter
        self.sticker_sender = sticker_sender
        self.file_system = file_system
        self.publish_event = publish_event
        self.logger = logger

    async def edit(
        self,
        chat_id: int,
        message_id: int,
        message: str = None,
        image_key: Optional[str] = None,
        fallback_image_key: Optional[str] = None,
        event_message_key: Optional[str] = None,
        reply_markup: Optional[Union[
            "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"
        ]] = None,
        parse_mode: Optional[str] = "HTML",
        always_show_photos: bool = False,
    ):
        """
        Попытаться отредактировать сообщение. Если редактирование невозможно — отправить новое (через send_message).
        :param always_show_photos: Будет показывать фото даже если стоит флаг Show == False
        :param event_message_key: ключ события, по которому отсылается стикер, если необходимо и при отсутствии image_key он занимает его место
        """

        try:
            if event_message_key:
                await self.sticker_sender.send(chat_id=chat_id, key=event_message_key)
        except StickerNotFound:
            pass

        image_key = self._resolve_image_key(image_key, event_message_key)

        # Если есть image_key — пробуем редактировать/заменить media
        if image_key:
            ui_image = await self.ui_images_service.get_ui_image(image_key)

            if ui_image and (ui_image.show or always_show_photos):
                file_path = self.path_builder.build_path_ui_image(file_name=ui_image.file_name)
                # сначала file_id
                if ui_image.file_id:
                    ok = await self._try_edit_media_by_file_id(
                        chat_id, message_id, ui_image.file_id, message, reply_markup, parse_mode
                    )
                    if ok:
                        return  # успешно
                    # пробуем редактировать media с загрузкой файла
                    ok = await self._try_edit_media_by_file(
                        chat_id, message_id, ui_image, message, reply_markup, parse_mode
                    )
                    if ok:
                        return  # успешно
                    # не удалось отредактировать — пробуем удалить старое и отправить новое
                    try:
                        await self.tg_client.delete_message(chat_id=chat_id, message_id=message_id)
                        self.logger.info(f"[edit_message] Deleted old message with media chat={chat_id} id={message_id}")
                    except Exception as e:
                        self.logger.warning(f"[edit_message] Failed to delete old message before resend: {e}")

                    await self.send_msg_service.send(
                        chat_id=chat_id,
                        message=message,
                        image_key=image_key,
                        fallback_image_key=fallback_image_key,
                        reply_markup=reply_markup
                        # указывать event_message_key не надо, т.к. может отослать два стикера
                    )
                    return
                elif self.file_system.exists(file_path):
                    # пробуем редактировать media с загрузкой файла
                    ok = await self._try_edit_media_by_file(
                        chat_id, message_id, ui_image, message, reply_markup, parse_mode
                    )
                    if ok:
                        return  # успешно
                    # не удалось отредактировать — пробуем удалить старое и отправить новое
                    try:
                        await self.tg_client.delete_message(chat_id=chat_id, message_id=message_id)
                        self.logger.info(f"[edit_message] Deleted old message with media chat={chat_id} id={message_id}")
                    except Exception as e:
                        self.logger.warning(f"[edit_message] Failed to delete old message before resend: {e}")

                    await self.send_msg_service.send(
                        chat_id=chat_id,
                        message=message,
                        image_key=image_key,
                        fallback_image_key=fallback_image_key,
                        reply_markup=reply_markup
                        # указывать event_message_key не надо, т.к. может отослать два стикера
                    )
                    return
                else:
                    text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{image_key}'"
                    await self.publish_event.create_ui_image(ui_image_key=ui_image.key)

            # если не нашли ui_image или не надо отсылать его (not ui_image.show)
            elif (not ui_image or ui_image and not ui_image.show) and fallback_image_key:
                text = ''
                if not ui_image:
                    text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{image_key}'"
                    self.logger.warning(text)

                # если не нашли ui_image или не надо отсылать его
                ui_image = await self.ui_images_service.get_ui_image(fallback_image_key)

                if ui_image:
                    file_path = self.path_builder.build_path_ui_image(file_name=ui_image.file_name)
                    if ui_image.file_id:
                        ok = await self._try_edit_media_by_file_id(
                            chat_id, message_id, ui_image.file_id, message, reply_markup, parse_mode
                        )
                        if ok:
                            if not ui_image:
                                await self.publish_event.send_log(
                                    text=text,
                                    log_lvl=LogLevel.WARNING
                                )
                            return  # успешно

                    elif self.file_system.exists(file_path):
                        # пробуем редактировать media с загрузкой файла
                        ok = await self._try_edit_media_by_file(
                            chat_id, message_id, ui_image, message, reply_markup, parse_mode
                        )
                        if ok:
                            if not ui_image:
                                await self.publish_event.send_log(
                                    text=text,
                                    log_lvl=LogLevel.WARNING
                                )
                            return  # успешно

                    else:
                        text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{fallback_image_key}'"
                        self.logger.warning(text)
                        await self.publish_event.create_ui_image(
                            ui_image_key=ui_image.key
                        )

                else:
                    await self.publish_event.send_log(
                        text=text,
                        log_lvl=LogLevel.WARNING
                    )
            elif not ui_image:
                # если нет замены для фото
                text = f"#Не_найдено_фото [edit_message]. \nget_ui_image='{image_key}'"
                await self.publish_event.send_log(
                    text=text,
                    log_lvl=LogLevel.WARNING
                )

            # если ui_image не найден или скрыт (show=False), то переходим к ветке "без фото"

        # --- Новое сообщение без фото ---
        # если старое было с фото — нужно удалить и отправить новое, т.к. нельзя удалить фото редактированием
        # попробуем сначала отредактировать текст; если ошибка "there is no text in the message to edit" → значит было фото
        text_result = await self._try_edit_text(chat_id, message_id, message, reply_markup, parse_mode)

        if text_result is True or text_result is None:
            return  # успешно отредактировали текст

        # не удалось отредактировать текст — удаляем и отправляем новое
        try:
            await self.tg_client.delete_message(chat_id=chat_id, message_id=message_id)
            self.logger.info(f"[edit_message] Deleted old message before sending new one chat={chat_id} id={message_id}")
        except Exception as e:
            self.logger.warning(f"[edit_message] Failed to delete old message before sending new one: {e}")

        await self.send_msg_service.send(
            chat_id=chat_id,
            message=message,
            image_key=image_key,
            fallback_image_key=fallback_image_key,
            reply_markup=reply_markup,
            parse_mode=parse_mode
            # указывать event_message_key не надо, т.к. может отослать два стикера
        )
        return


    def _resolve_image_key(self, image_key, event_message_key) -> str:
        return image_key or event_message_key

    async def _try_edit_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup,
        parse_mode: Optional[str] = "HTML"
    ) -> Optional[bool]:
        """
        Пробуем отредактировать текст. Возвращает:
          - True => успешно отредактировали
          - False => редактирование не удалось (например message not found)
          - None => сообщение не изменилось (message is not modified) — это не ошибка, но менять не нужно
        """
        try:
            if not text:
                text = "None"

            await self.tg_client.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True

        except TelegramBadRequestService as e:
            if self._is_message_not_modified_error(e):
                self.logger.debug(f"[edit_message] Message not modified chat={chat_id} id={message_id}")
                return None
            if self._is_message_not_found_error(e):
                self.logger.info(f"[edit_message] edit_message_text: message not found chat={chat_id} id={message_id}")
                return False
            if self._is_minor_errors(e):
                return False

            self.logger.exception(f"[edit_message] TelegramBadRequest editing text: {e}")
            return False

        except TelegramForbiddenErrorService as e:
            self.logger.warning(f"[edit_message] Forbidden editing text chat={chat_id} id={message_id}: {e}")
            return False
        except Exception as e:
            self.logger.exception(f"[edit_message] Unexpected error edit_message_text: {e}")
            return False

    async def _try_edit_media_by_file(
        self,
        chat_id: int,
        message_id: int,
        ui_image,
        caption: str,
        reply_markup,
        parse_mode: Optional[str] = "HTML",
        fallback_image_key: Optional[str] = None,
    ) -> bool:
        """Пробуем заменить media, загрузив файл с диска. При успехе сохраняем новый file_id (если есть)."""

        file_path = self.path_builder.build_path_ui_image(file_name=ui_image.file_name)

        try:
            msg = await self.tg_client.edit_message_photo(
                chat_id=chat_id,
                message_id=message_id,
                data=EditMessagePhoto(
                    file_path=file_path,
                    reply_markup=reply_markup,
                    caption=caption,
                    parse_mode=parse_mode
                )
            )
            # извлекаем новый file_id если он есть
            try:
                if hasattr(msg, "photo") and msg.photo:
                    new_file_id = msg.photo[-1].file_id
                    if new_file_id:
                        await self.ui_images_service.update_ui_image(
                            key=ui_image.key, data=UpdateUiImageDTO(file_id=new_file_id),
                            make_commit=True, filling_redis=True
                        )
            except TelegramBadRequestService as e:
                # это не критичные ошибки
                if 'canceled by new editMessageMedia request' in e.message or 'message is not modified' in e.message:
                    return True  # это сообщение уже обработано или не надо обрабатывать
                else:
                    self.logger.exception("[edit_message] Failed to extract/save new file_id after edit_message_media")
            except Exception:
                self.logger.exception("[edit_message] Failed to extract/save new file_id after edit_message_media")
            return True

        except (FileNotFoundError, AttributeError):
            self.logger.warning(f"[edit_message] Local file not found: {file_path}")
            await self.publish_event.create_ui_image(ui_image_key=ui_image.key)

            if fallback_image_key:
                ui_image = await self.ui_images_service.get_ui_image(fallback_image_key)

                if ui_image:
                    file_path = self.path_builder.build_path_ui_image(file_name=ui_image.file_name)
                    if ui_image.file_id:
                        ok = await self._try_edit_media_by_file_id(
                            chat_id, message_id, ui_image.file_id, caption, reply_markup
                        )
                        if ok:
                            return True  # успешно

                    if not self.file_system.exists(file_path):
                        await self.publish_event.create_ui_image(ui_image_key=ui_image.key)
                        await self.publish_event.send_log(
                            text=f"#Не_найдено_фото [edit_message]. \nget_ui_image='{ui_image.key}'",
                            log_lvl=LogLevel.WARNING
                        )
                    else:
                        ok = await self._try_edit_media_by_file(chat_id, message_id, ui_image, caption, reply_markup)
                        if ok:
                            return True  # успешно

            return False

        except TelegramBadRequestService as e:
            if self._is_message_not_found_error(e):
                self.logger.info(
                    f"[edit_message] edit_message_media (upload) message not found, chat={chat_id} id={message_id}")
            else:
                self.logger.exception(f"[edit_message] edit_message_media (upload) failed: {e}")
            return False
        except TelegramForbiddenErrorService as e:
            self.logger.warning(f"[edit_message] Forbidden editing media (upload): {e}")
            return False
        except Exception as e:
            self.logger.exception(f"[edit_message] Unexpected error editing media (upload): {e}")
            return False

    async def _try_edit_media_by_file_id(
        self,
        chat_id: int,
        message_id: int,
        file_id: str,
        caption: str,
        reply_markup,
        parse_mode: Optional[str] = "HTML"
    ) -> bool:
        """Пробуем заменить media по существующему file_id. Возвращаем True при успехе."""
        try:
            await self.tg_client.edit_message_photo(
                chat_id=chat_id,
                message_id=message_id,
                data=EditMessagePhoto(
                    file_id=file_id,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    caption=caption,
                )
            )
            return True
        except ValidationError:  # если текс не передан
            return False
        except TelegramForbiddenErrorService as e:
            self.logger.warning(f"[edit_message] Forbidden editing media by file_id chat={chat_id} id={message_id}: {e}")
            return False
        except TelegramBadRequestService as e:
            # это не критичные ошибки
            if 'canceled by new editMessageMedia request' in e.message or 'message is not modified' in e.message:
                return True  # это сообщение уже обработано или не надо обрабатывать
            elif self._is_file_id_invalid_error(e):
                self.logger.info(f"[edit_message] file_id invalid for file_id={file_id}; will try upload. Detail: {e}")
            elif self._is_message_not_found_error(e):
                self.logger.info(f"[edit_message] message not found when editing media by file_id chat={chat_id} id={message_id}")
            else:
                self.logger.exception(f"[edit_message] TelegramBadRequest editing by file_id: {e}")
            return False
        except Exception as e:
            self.logger.exception(f"[edit_message] Unexpected error editing media by file_id: {e}")
            return False

    def _is_message_not_found_error(self, exc: Exception) -> bool:
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

    def _is_message_not_modified_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return "message is not modified" in text or "message text is not modified" in text

    def _is_minor_errors(self, exc: Exception) -> bool:
        text = str(exc).lower()
        phrases = [
            # если пытаемся отредактировать сообщение с фото на сообщение без фото (такие только удалять)
            "there is no text in the message to edit",
        ]
        return any(p in text for p in phrases)

    def _is_file_id_invalid_error(self, exc: Exception) -> bool:
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



