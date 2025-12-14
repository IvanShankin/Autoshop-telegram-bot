from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


def admin_statistics_kb(language: str, current_days: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", "Per day"),
                callback_data=f'admin_statistics:1' if current_days != 1 else "none"
            ),
            InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", "Per week"),
                callback_data=f'admin_statistics:7' if current_days != 7 else "none"
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", "Per month"),
                callback_data=f'admin_statistics:30' if current_days != 30 else "none"
            ),
            InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", "Per year"),
                callback_data=f'admin_statistics:365' if current_days != 365 else "none"
            ),
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "All time"),
            callback_data=f'admin_statistics:99999' if current_days != 99999 else "none"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'admin_panel'
        )]
    ])