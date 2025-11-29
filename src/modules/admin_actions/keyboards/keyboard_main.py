from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import get_text


def main_admin_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Category Editor"),
            callback_data='editors'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'User management'),
            callback_data="get_id_or_user_user_management"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Settings'),
            callback_data="admin_settings"
        )]
    ])

def back_in_main_admin_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Back"),
            callback_data='admin_panel'
        )]
    ])