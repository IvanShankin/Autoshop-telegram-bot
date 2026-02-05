from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot_actions.bot_instance import get_bot
from src.services.database.categories.actions import get_categories
from src.services.database.categories.models import CategoryFull
from src.services.database.system.actions import get_settings
from src.utils.i18n import get_text


async def subscription_prompt_kb(language: str):
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
        keyboard.row(InlineKeyboardButton(text=get_text(language, 'kb_catalog','Channel'),url=url))
    keyboard.row(InlineKeyboardButton(text=get_text(language, 'kb_general','Skip'),callback_data='skip_subscription'))

    keyboard.adjust(1)

    return keyboard.as_markup()


async def main_categories_kb(language: str) ->  InlineKeyboardMarkup:
    categories = await get_categories(language=language)
    keyboard = InlineKeyboardBuilder()

    for cat in categories:
        keyboard.add(InlineKeyboardButton(text=cat.name, callback_data=f'show_category:{cat.category_id}:0'))

    keyboard.adjust(1)
    return keyboard.as_markup()


async def account_category_kb(
    language: str,
    category: CategoryFull,
    quantity_for_buying: int = 0,
    promo_code_id: int = None
) ->  InlineKeyboardMarkup:
    parent_category = category
    keyboard = InlineKeyboardBuilder()
    current_category_id = parent_category.category_id

    if parent_category.is_product_storage: # если в этой категории продаются товары
        if category.allow_multiple_purchase:
            keyboard.row(
                InlineKeyboardButton(
                    # callback_data - "show_category:{id категории}:{количество аккаунтов}"
                    text="—", callback_data=f'show_category:{current_category_id}:{quantity_for_buying - 1}'
                ),
                InlineKeyboardButton(text=str(quantity_for_buying), callback_data=f'none'),
                InlineKeyboardButton(
                    text="+", callback_data=f'show_category:{current_category_id}:{quantity_for_buying + 1}'
                ),
            )

        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'kb_catalog', 'Buy'),
            # callback_data - "confirm_buy_acc:{id категории}:{количество аккаунтов}:{id промокода(если есть)}"
            callback_data=f'confirm_buy_category:{current_category_id}:{quantity_for_buying}:{promo_code_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'kb_catalog', 'Enter promo code'),
            # callback_data - "enter_promo:{id категории}:{количество аккаунтов}"
            callback_data=f'enter_promo:{current_category_id}:{quantity_for_buying}')
        )
    else: # если эта категория хранит другие категории
        categories = await get_categories(
            parent_id=current_category_id,
            language=language
        )

        buttons_in_row = max(1, min(8, parent_category.number_buttons_in_row)) # # ограничим от 1 до 8

        # Добавляем кнопки в билдер
        buttons = [
            InlineKeyboardButton(
                text=cat.name,
                callback_data=f'show_category:{cat.category_id}:0'
            )
            for cat in categories
        ]

        # размещаем по N кнопок в строке
        for i in range(0, len(buttons), buttons_in_row):
            keyboard.row(*buttons[i:i + buttons_in_row])

    if parent_category.is_main: # если это главная категория, то вернём в выбор сервиса
        keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'show_main_categories'))
    else:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'show_category:{parent_category.parent_id}:0')
        )

    return keyboard.as_markup()


def confirm_buy_kb(
    language: str,
    category_id: int,
    quantity_for_buying: int = 0,
    promo_code_id: int = 0
) ->  InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
            # callback_data - "buy_category:{id категории}:{количество аккаунтов}:{id промокода(если есть)}"
            text=get_text(language, "kb_general", "Confirm"), callback_data=f'buy_in_category:{category_id}:{quantity_for_buying}:{promo_code_id}'
            ),
            InlineKeyboardButton(
                text=get_text(language, "kb_general", "Back"), callback_data=f'show_category:{category_id}:{quantity_for_buying}'
            ),
        ]
    ])


def back_in_account_category_kb(
    language: str,
    category_id: int,
    quantity_for_buying: int = 0
) ->  InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"), callback_data=f'show_category:{category_id}:{quantity_for_buying}'
        )]
    ])


def replenishment_and_back_in_cat(
    language: str,
    category_id: int,
    quantity_for_buying: int = 0
) ->  InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Top up your balance'), callback_data='show_type_replenishment')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'show_category:{category_id}:{quantity_for_buying}')]
    ])

