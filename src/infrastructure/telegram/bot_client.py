from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError, TelegramNotFound, \
    TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply, \
    Message, FSInputFile, InputMediaPhoto, ReactionTypeEmoji, InlineKeyboardButton, BufferedInputFile

from src.exceptions.telegram import TelegramBadRequestService, TelegramAPIErrorService, TelegramForbiddenErrorService, \
    TelegramNotFoundService, TelegramRetryAfterService
from src.models.telegram import InlineKeyboardMarkupService
from src.models.update_models.bot_actions import EditMessagePhoto


def handle_telegram_errors(func):
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except Exception as e:
            for exc, mapped in self.ERROR_MAP.items():
                if isinstance(e, exc):
                    raise mapped(str(e)) from e
            raise

    return wrapper


class TelegramClient:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.ERROR_MAP = {
            TelegramBadRequest: TelegramBadRequestService,
            TelegramAPIError: TelegramAPIErrorService,
            TelegramForbiddenError: TelegramForbiddenErrorService,
            TelegramNotFound: TelegramNotFoundService,
            TelegramRetryAfter: TelegramRetryAfterService,
        }

    async def _call(self, method, *args, **kwargs):
        try:
            return await method(*args, **kwargs)

        except Exception as e:
            # ищем, нужно ли маппить на сервисное исключение
            for exc, mapped in self.ERROR_MAP.items():
                if isinstance(e, exc):
                    # создаём сервисное исключение с оригинальным сообщением
                    raise mapped(str(e)) from e
            # если не нашли — пробрасываем оригинальное
            raise

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
        message_effect_id: Optional[str] = None,
    ) -> Message:
        return await self._call(
            self.bot.send_message,
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            message_effect_id=message_effect_id,
        )

    async def send_sticker(self, chat_id: int, file_id: str) ->  Message:
        return await self._call(
            self.bot.send_sticker,
            chat_id=chat_id,
            sticker=file_id,
        )

    async def send_photo(
        self,
        chat_id: int | str,
        file_path: Optional[str | Path] = None,
        file_id: Optional[str] = None,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
        message_effect_id: Optional[str] = None,
    ) ->  Message:
        if not file_id and not file_path:
            raise ValueError(f"Необходимо хотя бы одно из этого: 'file_path', 'file_id' ")

        photo = file_id if file_id else FSInputFile(file_path)

        return await self._call(
            self.bot.send_photo,
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            message_effect_id=message_effect_id,
        )

    async def send_animation(
        self,
        chat_id: int,
        animation: str | FSInputFile,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[
        InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply] = None,
    ) -> Message:
        return await self._call(
            self.bot.send_animation,
            chat_id=chat_id,
            animation=animation,
            caption=caption or "",
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )

    async def send_video(
        self,
        chat_id: int,
        video: str | FSInputFile,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply] = None,
    ) -> Message:
        return await self._call(
            self.bot.send_video,
            chat_id=chat_id,
            video=video,
            caption=caption or "",
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )

    async def send_document(
        self,
        chat_id: int,
        document: str | FSInputFile | BufferedInputFile,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply] = None,
    ) -> Message:
        return await self._call(
            self.bot.send_document,
            chat_id=chat_id,
            document=document,
            caption=caption or "",
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )

    async def edit_message_text(
        self,
        text: str,
        chat_id: int | str,
        message_id: int | str,
        parse_mode: Optional[str] = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    ) -> Message | bool:
        return await self._call(
            self.bot.edit_message_text,
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )

    async def edit_message_photo(
        self,
        chat_id: int | str,
        message_id: int | str,
        data: EditMessagePhoto,
    ):
        if not data.file_id and not data.file_path:
            raise ValueError(f"Необходимо хотя бы одно из этого: 'file_path', 'file_id' ")

        if data.file_path:
            media = await self.get_input_file(data.file_path)
        else:
            media = data.file_id

        media = InputMediaPhoto(media=media, caption=data.caption, parse_mode=data.parse_mode)
        return await self._call(
            self.bot.edit_message_media,
            chat_id=chat_id,
            message_id=message_id,
            media=media,
            reply_markup=data.reply_markup
        )

    @handle_telegram_errors
    async def get_input_file(self, file_path: str | Path) -> FSInputFile:
        return FSInputFile(file_path)

    @handle_telegram_errors
    async def get_inline_keyboard_markup(
        self,
        inline_keyboard: InlineKeyboardMarkupService
    ) -> InlineKeyboardMarkup:

        keyboard = []

        for row in inline_keyboard.inline_keyboard:
            buttons_row = []
            for button in row:
                buttons_row.append(
                    InlineKeyboardButton(
                        text=button.text,
                        url=button.url
                    )
                )
            keyboard.append(buttons_row)

        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    async def set_reaction(self, chat_id: int, message_id: int):
        return await self._call(
            self.bot.set_message_reaction,
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji="❤️")],
            is_big=True  # ВАЖНО: включает фонтан
        )

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        return await self._call(
            self.bot.delete_message,
            chat_id=chat_id,
            message_id=message_id
        )