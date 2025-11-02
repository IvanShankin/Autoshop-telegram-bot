from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.i18n import get_i18n

def catalog_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Accounts'), callback_data='show_main_catalog_account')],
    ])
