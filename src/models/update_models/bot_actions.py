from pathlib import Path
from typing import Optional, TYPE_CHECKING, Union

from pydantic import BaseModel


if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply


class EditMessagePhoto(BaseModel):
    caption: Optional[str] = None
    parse_mode: Optional[str | Path] = None
    file_path: Optional[str | Path] = None
    file_id: Optional[str] = None
    reply_markup: Optional[Union[
        "InlineKeyboardMarkup", "ReplyKeyboardMarkup", "ReplyKeyboardRemove", "ForceReply"
    ]] = None,
