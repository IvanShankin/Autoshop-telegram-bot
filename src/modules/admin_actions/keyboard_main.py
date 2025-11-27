from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


async def main_admin_kb(language: str):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=get_text(language, 'keyboard','Category Editor'), callback_data="category_editor"))
    keyboard.adjust(1)
    return keyboard.as_markup()