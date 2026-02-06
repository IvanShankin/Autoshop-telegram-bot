from aiogram.types import InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from src.services.database.admins.actions import check_admin
from src.services.database.system.actions import get_settings
from src.utils.i18n import get_text


selecting_language = InlineKeyboardMarkup(
    inline_keyboard = [
            [InlineKeyboardButton(text = "Русский", callback_data="set_language_after_start:ru")],
            [InlineKeyboardButton(text = "English", callback_data="set_language_after_start:en")]
        ],
)

async def main_kb(language: str, user_id: int):
    keyboard_builder = ReplyKeyboardBuilder()

    keyboard_builder.row(KeyboardButton(text = get_text(language, 'kb_start', "product_categories")))
    keyboard_builder.row(
        KeyboardButton(text = get_text(language, 'kb_start', "profile")),
        KeyboardButton(text = get_text(language, 'kb_start', 'information'))
    )
    if await check_admin(user_id):
        keyboard_builder.row(KeyboardButton(text=get_text(language, 'kb_start', "admin_panel")))

    return keyboard_builder.as_markup(resize_keyboard=True)


async def support_kb(language: str, support_username: str = None):
    if not support_username:
        settings = await get_settings()
        support_username = settings.support_username

    if not support_username:
        return None

    support_name = get_text(language, 'kb_start', "support")

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text=support_name, url=f"https://t.me/{support_username.lstrip()}"))
    keyboard.adjust(1)
    return keyboard.as_markup()
