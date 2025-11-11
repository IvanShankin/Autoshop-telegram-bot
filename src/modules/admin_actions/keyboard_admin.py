from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_i18n


async def main_admin_kb(language: str):
    i18n = get_i18n(language, 'keyboard')

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=i18n.gettext('Category Editor'), callback_data="category_editor"))
    keyboard.adjust(1)
    return keyboard.as_markup()