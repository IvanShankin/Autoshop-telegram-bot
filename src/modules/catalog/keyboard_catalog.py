from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot_actions.bot_instance import get_bot
from src.services.database.system.actions import get_settings
from src.utils.i18n import get_i18n

def catalog_kb(language: str):
    i18n = get_i18n(language, 'keyboard')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Accounts'), callback_data='show_catalog_services_accounts')],
    ])

async def subscription_prompt_kb(language: str):
    i18n = get_i18n(language, 'keyboard')
    settings = await get_settings()
    bot = await get_bot()

    url = None
    if settings.channel_for_subscription_url:
        url = settings.channel_for_subscription_url
    elif settings.channel_for_subscription_id:
        channel = await bot.get_chat(settings.channel_for_subscription_id)
        url = f'https://t.me/{channel.username}'


    keyboard = InlineKeyboardBuilder()
    if url:
        keyboard.row(InlineKeyboardButton(text=i18n.gettext('Channel'),url=url))
    keyboard.row(InlineKeyboardButton(text=i18n.gettext('Skip'),callback_data='skip_subscription'))

    keyboard.adjust(1)

    return keyboard.as_markup()
