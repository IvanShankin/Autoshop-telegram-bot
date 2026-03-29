from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply, \
    Message, FSInputFile, InputMediaPhoto, ReactionTypeEmoji

from src.models.update_models.bot_actions import EditMessagePhoto


class TelegramClient:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
        message_effect_id: Optional[str] = None,
    ) -> Message:
        return await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            message_effect_id=message_effect_id,
        )

    async def send_sticker(self, chat_id: int, file_id: str) ->  Message:
        return await self.bot.send_sticker(chat_id=chat_id, sticker=file_id)

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

        return await self.bot.send_photo(
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
        return await self.bot.send_animation(
            chat_id=chat_id, animation=animation, caption=caption or "",
            parse_mode=parse_mode, reply_markup=reply_markup
        )

    async def send_video(
        self,
        chat_id: int,
        video: str | FSInputFile,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply] = None,
    ) -> Message:
        return await self.bot.send_video(
            chat_id=chat_id, video=video, caption=caption or "",
            parse_mode=parse_mode, reply_markup=reply_markup
        )

    async def send_document(
        self,
        chat_id: int,
        document: str | FSInputFile,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply] = None,
    ) -> Message:
        return await self.bot.send_document(
            chat_id=chat_id, document=document, caption=caption or "",
            parse_mode=parse_mode, reply_markup=reply_markup
        )

    async def edit_message_text(
        self,
        text: str,
        chat_id: int | str,
        message_id: int | str,
        parse_mode: Optional[str] = None,
        reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    ) -> Message | bool:
        return await self.bot.edit_message_text(
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
            media = self.get_input_file(data.file_path)
        else:
            media = data.file_id

        media = InputMediaPhoto(media=media, caption=data.caption, parse_mode=data.parse_mode)
        return await self.bot.edit_message_media(
            chat_id=chat_id,
            message_id=message_id,
            media=media,
            reply_markup=data.reply_markup
        )

    def get_input_file(self, file_path: str | Path) -> FSInputFile:
        return FSInputFile(file_path)

    async def set_reaction(self, chat_id: int, message_id: int):
        await self.bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji="❤️")],
            is_big=True  # ВАЖНО: включает фонтан
        )

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        return await self.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )