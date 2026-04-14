from aiogram.types import InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from src.application.models.modules import AdminModule
from src.infrastructure.telegram.bot_instance import get_bot
from src.utils.i18n import get_text


selecting_language = InlineKeyboardMarkup(
    inline_keyboard = [
            [InlineKeyboardButton(text = "Русский", callback_data="set_language_after_start:ru")],
            [InlineKeyboardButton(text = "English", callback_data="set_language_after_start:en")]
        ],
)

async def main_kb(language: str, user_id: int, admin_module: AdminModule):
    keyboard_builder = ReplyKeyboardBuilder()

    keyboard_builder.row(KeyboardButton(text = get_text(language, 'kb_start', "product_categories")))
    keyboard_builder.row(
        KeyboardButton(text = get_text(language, 'kb_start', "profile")),
        KeyboardButton(text = get_text(language, 'kb_start', 'information'))
    )
    if await admin_module.admin_service.check_admin(user_id):
        keyboard_builder.row(KeyboardButton(text=get_text(language, 'kb_start', "admin_panel")))

    return keyboard_builder.as_markup(resize_keyboard=True)


async def info_kb(language: str,  admin_module: AdminModule):
    settings = await admin_module.settings_service.get_settings()
    bot = get_bot()
    keyboard = InlineKeyboardBuilder()

    url_channel = None
    if settings.channel_for_subscription_url:
        url_channel = settings.channel_for_subscription_url
    elif settings.channel_for_subscription_id:
        channel = await bot.get_chat(settings.channel_for_subscription_id)
        url_channel = f'https://t.me/{channel.username}'

    if settings.support_username:
        keyboard.add(
            InlineKeyboardButton(
                text=get_text(language, 'kb_start', "support"),
                url=f"https://t.me/{settings.support_username.lstrip()}"
            )
        )

    if url_channel:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_catalog", "channel"),
                url=url_channel
            )
        )

    if settings.FAQ:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_catalog", "faq"),
                url=settings.FAQ
            )
        )

    keyboard.adjust(1)
    return keyboard.as_markup()