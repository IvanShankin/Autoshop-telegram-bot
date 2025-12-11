from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


def admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language,'keyboard',"Change"),
            callback_data=f"change_admin_settings"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Add admin"),
            callback_data=f"add_admin"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Delete admin"),
            callback_data=f"delete_admin"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Download logs"),
            callback_data=f"download_logs"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Back"),
            callback_data=f"admin_panel"
        )],

    ])


def change_admin_settings_kb(language: str, current_maintenance_mode: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(
                language,
                'keyboard',
                "{indicator} maintenance mode"
            ).format(indicator='🟢' if current_maintenance_mode else '🔴'),
            callback_data=f'update_maintenance_mode:{0 if current_maintenance_mode else 1}'
        )],
        [InlineKeyboardButton(
            text=get_text(language,'keyboard',"Support username"),
            callback_data=f'update_support_username'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Chat ID for logging"),
            callback_data=f'update_channel_for_logging_id'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Channel ID to subscribe to"),
            callback_data=f'update_channel_for_subscription_id'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "URL channel for subscription"),
            callback_data=f'update_channel_for_subscription_url'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Channel name"),
            callback_data=f'update_channel_name'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Shop name"),
            callback_data=f'update_shop_name'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "URL to FAQ"),
            callback_data=f'update_faq'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"admin_settings"
        )],
    ])


def back_in_change_admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"change_admin_settings"
        )],
    ])


def back_in_admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"admin_settings"
        )],
    ])

