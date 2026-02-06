from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import get_text


def main_admin_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "editors"),
            callback_data='editors'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "user_management"),
            callback_data="get_id_or_user_user_management"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "showing_data_by_id"),
            callback_data="data_by_id:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "statistics"),
            callback_data="admin_statistics:99999"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_profile", "settings"),
            callback_data="admin_settings"
        )]
    ])

def back_in_main_admin_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data='admin_panel'
        )]
    ])