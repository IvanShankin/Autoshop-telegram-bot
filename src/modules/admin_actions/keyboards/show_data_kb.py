from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


def admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language,"kb_admin_panel","Change"),
            callback_data=f"change_admin_settings"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Add admin"),
            callback_data=f"add_admin"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Delete admin"),
            callback_data=f"delete_admin"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Download logs"),
            callback_data=f"download_logs"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"admin_panel"
        )]
    ])
