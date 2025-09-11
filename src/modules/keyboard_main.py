from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.services.system.actions import get_settings
from src.i18n import get_i18n


async def support_kb(language: str, support_username: str = None):
    if not support_username:
        settings = await get_settings()
        support_username = settings.support_username

    i18n = get_i18n(language, 'keyboard_dom')
    support_name = i18n.gettext('Support')

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=support_name, url=f"https://t.me/{support_username.lstrip()}"))
    keyboard.adjust(1)
    return keyboard.as_markup()
