from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import PAGE_SIZE
from src.services.database.discounts.actions.actions_promo import get_promo_code_by_page, get_count_promo_codes
from src.services.database.discounts.models import PromoCodes
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.utils.i18n import get_text


def admin_promo_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"Create promo code"), callback_data=f'admin_create_promo'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"Promo codes"), callback_data=f'admin_promo_list:1:0'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'editors'),]
    ])


async def all_admin_promo_kb(current_page: int, language: str, show_not_valid: bool):
    """Клавиатура со списком только активных ваучеров у администрации"""
    records = await get_promo_code_by_page(page=current_page, page_size=PAGE_SIZE, show_not_valid=show_not_valid)
    total = await get_count_promo_codes(consider_invalid=show_not_valid)
    total_pages = max(ceil(total / PAGE_SIZE), 1)

    def item_button(promo_code: PromoCodes):
        valid = get_text(language, "keyboard", "Valid" if promo_code.is_valid else "Not valid")
        return InlineKeyboardButton(
            text=f"{valid}  —  {promo_code.activation_code}",
            callback_data=f"show_admin_promo:{current_page}:{int(show_not_valid)}:{promo_code.promo_code_id}"
        )

    return pagination_keyboard(
        records,
        current_page,
        total_pages,
        item_button,
        left_prefix=f"admin_promo_list:{int(show_not_valid)}",
        right_prefix=f"admin_promo_list:{int(show_not_valid)}",
        back_text=get_text(language, 'keyboard', 'Back'),
        back_callback="admin_promo",
        helpers_text=get_text(
            language, 'keyboard', "Show not valid {indicator}"
        ).format(indicator='🟢' if show_not_valid else '🔴'),
        helpers_callback=f"admin_promo_list:{0 if show_not_valid else 1}:1"
    )


def select_promo_code_type_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"With a fixed amount"), callback_data=f'create_promo_code_amount'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"With percentage"), callback_data=f'create_promo_code_percentage'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'admin_promo'),]
    ])


def skip_number_activations_promo_or_in_start_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard', "Skip"), callback_data=f"set_expire_at_promo"), ],
        [InlineKeyboardButton(text=get_text(language, 'keyboard', "In start"), callback_data=f"admin_create_promo"), ],
    ])


def skip_expire_at_promo_or_in_start_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard', "Skip"), callback_data=f"set_min_order_amount_promo"), ],
        [InlineKeyboardButton(text=get_text(language, 'keyboard', "In start"), callback_data=f"admin_create_promo"), ],
    ])


def show_admin_promo_kb(language: str, current_page: int, promo_code_id: int, show_not_valid: bool, is_valid: bool):
    keyboard = InlineKeyboardBuilder()

    if is_valid:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Deactivate"),
            callback_data=f'confirm_deactivate_promo_code:{promo_code_id}:{int(show_not_valid)}:{current_page}'
        ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', "Back"),
        callback_data=f'admin_promo_list:{int(show_not_valid)}:{current_page}'
    ))
    return keyboard.as_markup()


def in_show_admin_promo_kb(language: str, current_page: int, promo_code_id: int, show_not_valid: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "In promo code"),
            callback_data=f"show_admin_promo:{current_page}:{int(show_not_valid)}:{promo_code_id}"
        ), ],
    ])


def confirm_deactivate_promo_code_kb(language: str, current_page: int, promo_code_id: int, show_not_valid: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
                text=get_text(language, 'keyboard', 'Confirm'),
                callback_data=f'deactivate_promo_code:{promo_code_id}:{int(show_not_valid)}:{current_page}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"admin_promo_list:{int(show_not_valid)}:{current_page}"
        )]
    ])


def back_in_all_admin_promo_kb(language: str, current_page: int, show_not_valid: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"admin_promo_list:{int(show_not_valid)}:{current_page}"
        )]
    ])


def back_in_admin_promo_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard', "Back"), callback_data=f"admin_promo"),],
    ])


def back_in_start_creating_promo_code_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard', "In start"), callback_data=f"admin_create_promo"),],
    ])


