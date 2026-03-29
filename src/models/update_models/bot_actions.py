from pathlib import Path
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply
from pydantic import BaseModel


class EditMessagePhoto(BaseModel):
    caption: Optional[str] = None
    parse_mode: Optional[str | Path] = None
    file_path: Optional[str | Path] = None
    file_id: Optional[str] = None
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None
