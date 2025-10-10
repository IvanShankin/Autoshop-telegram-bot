from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.services.system.actions import get_settings
from src.utils.i18n import get_i18n


selecting_language = InlineKeyboardMarkup(
    inline_keyboard = [
            [InlineKeyboardButton(text = "Русский", callback_data="set_language_after_start:ru")],
            [InlineKeyboardButton(text = "English", callback_data="set_language_after_start:en")]
        ],
)

def main_kb(language):
    i18n = get_i18n(language, 'keyboard_dom')
    catalog = i18n.gettext('Product catalog')
    profile = i18n.gettext('Profile')
    information = i18n.gettext('Information')
    return ReplyKeyboardMarkup(
        keyboard = [
            [KeyboardButton(text = catalog)],
            [KeyboardButton(text = profile), KeyboardButton(text = information)]
        ],
        resize_keyboard=True,
        input_field_placeholder='Воспользуйтесь меню'
    )

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
