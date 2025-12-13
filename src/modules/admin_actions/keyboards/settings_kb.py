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
        )],

    ])


def change_admin_settings_kb(language: str, current_maintenance_mode: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(
                language,
                "kb_admin_panel",
                "{indicator} maintenance mode"
            ).format(indicator='🟢' if current_maintenance_mode else '🔴'),
            callback_data=f'update_maintenance_mode:{0 if current_maintenance_mode else 1}'
        )],
        [InlineKeyboardButton(
            text=get_text(language,'kb_start',"Support username"),
            callback_data=f'update_support_username'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Chat ID for logging"),
            callback_data=f'update_channel_for_logging_id'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Channel ID to subscribe to"),
            callback_data=f'update_channel_for_subscription_id'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "URL channel for subscription"),
            callback_data=f'update_channel_for_subscription_url'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Channel name"),
            callback_data=f'update_channel_name'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Shop name"),
            callback_data=f'update_shop_name'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "URL to FAQ"),
            callback_data=f'update_faq'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"admin_settings"
        )],
    ])


def back_in_change_admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"change_admin_settings"
        )],
    ])


def back_in_admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"admin_settings"
        )],
    ])

