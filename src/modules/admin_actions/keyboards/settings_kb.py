from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


def admin_settings_kb(language: str, current_maintenance_mode: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(
                language,
                'keyboard',
                "{indicator} maintenance mode"
            ).format(indicator='🟢' if current_maintenance_mode else '🔴'),
            callback_data=f'update_maintenance_mode:{current_maintenance_mode}:{0 if current_maintenance_mode else 1}'
        )],
        # ДОПИСАТЬ
        # ДОПИСАТЬ
        # ДОПИСАТЬ
    ])


def back_in_admin_set_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"user_management:{user_id}"
        )],
    ])

