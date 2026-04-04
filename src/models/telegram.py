from typing import Optional, List

from pydantic import BaseModel


class InlineKeyboardButtonService(BaseModel):
    text: Optional[str] = None
    url: Optional[str] = None


class InlineKeyboardMarkupService(BaseModel):
    inline_keyboard: List[List[InlineKeyboardButtonService]]