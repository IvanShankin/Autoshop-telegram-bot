from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


def admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language,"kb_admin_panel","change"),
            callback_data=f"change_admin_settings"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "add_admin"),
            callback_data=f"add_admin"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "delete_admin"),
            callback_data=f"delete_admin"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "download_logs"),
            callback_data=f"download_logs"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"admin_panel"
        )],

    ])


def change_admin_settings_kb(language: str, current_maintenance_mode: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(
                language,
                "kb_admin_panel",
                "maintenance_mode_indicator"
            ).format(indicator='🟢' if current_maintenance_mode else '🔴'),
            callback_data=f'update_maintenance_mode:{0 if current_maintenance_mode else 1}'
        )],
        [InlineKeyboardButton(
            text=get_text(language,'kb_start',"support_username"),
            callback_data=f'update_support_username'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "chat_id_for_logging"),
            callback_data=f'update_channel_for_logging_id'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "channel_id_to_subscribe_to"),
            callback_data=f'update_channel_for_subscription_id'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "url_channel_for_subscription"),
            callback_data=f'update_channel_for_subscription_url'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "channel_name"),
            callback_data=f'update_channel_name'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "shop_name"),
            callback_data=f'update_shop_name'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "url_to_faq"),
            callback_data=f'update_faq'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"admin_settings"
        )],
    ])


def back_in_change_admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"change_admin_settings"
        )],
    ])


def back_in_admin_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"admin_settings"
        )],
    ])

