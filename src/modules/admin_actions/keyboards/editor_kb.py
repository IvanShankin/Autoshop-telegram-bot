from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.i18n import get_text


def choice_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Services and Categories'), callback_data=f'services_editor'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Replenishments'), callback_data=f'replenishment_editor'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Images'), callback_data=f'images_editor'),]
    ])
