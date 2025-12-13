from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import get_text


def main_admin_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Editors"),
            callback_data='editors'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'User management'),
            callback_data="get_id_or_user_user_management"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Showing data by ID"),
            callback_data="show_data_by_id"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'kb_profile', 'Settings'),
            callback_data="admin_settings"
        )]
    ])

def back_in_main_admin_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data='admin_panel'
        )]
    ])