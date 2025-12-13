from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import PAGE_SIZE
from src.services.database.discounts.actions import get_valid_voucher_by_page, get_count_voucher
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.utils.i18n import get_text


def admin_vouchers_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile',"Create voucher"), callback_data=f'admin_create_voucher'),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","Vouchers"), callback_data=f'admin_voucher_list:1'),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editors'),]
    ])


def skip_number_activations_or_back_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_general', "Skip"), callback_data=f"set_expire_at"), ],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f"admin_vouchers"), ],
    ])


def skip_expire_at_or_back_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_general', "Skip"), callback_data=f"set_amount_admin_voucher"), ],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f"admin_vouchers"), ],
    ])


async def all_admin_vouchers_kb(current_page: int, language: str):
    """Клавиатура со списком только активных ваучеров у администрации"""
    records = await get_valid_voucher_by_page(page=current_page, page_size=PAGE_SIZE, only_created_admin=True)
    total = await get_count_voucher(by_admins=True)
    total_pages = max(ceil(total / PAGE_SIZE), 1)

    def item_button(voucher):
        valid = get_text(language, "kb_admin_panel", "Valid" if voucher.is_valid else "Not valid")
        return InlineKeyboardButton(
            text=f"{valid}   {voucher.amount} ₽   {voucher.activation_code}",
            callback_data=f"show_admin_voucher:{current_page}:{voucher.voucher_id}"
        )

    return pagination_keyboard(
        records,
        current_page,
        total_pages,
        item_button,
        left_prefix=f"admin_voucher_list",
        right_prefix=f"admin_voucher_list",
        back_text=get_text(language, "kb_general", "Back"),
        back_callback="admin_vouchers",
    )


def show_admin_voucher_kb(language: str, current_page: int, voucher_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'kb_profile', 'Deactivate'),
            callback_data=f'confirm_deactivate_admin_voucher:{voucher_id}:{current_page}'
        ),],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'admin_voucher_list:{current_page}'
        ),],
    ])


def in_admin_voucher_kb(language: str, current_page: int, voucher_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "In voucher"),
            callback_data=f"show_admin_voucher:{current_page}:{voucher_id}"
        ), ],
    ])


def back_in_all_admin_voucher_kb(language: str, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'admin_voucher_list:{current_page}'
        )]
    ])

def confirm_deactivate_admin_voucher_kb(language: str, current_page: int, voucher_id: int, is_valid: bool):
    keyboard = InlineKeyboardBuilder()

    if is_valid:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'kb_profile', "Deactivate"),
            callback_data=f'deactivate_admin_voucher:{voucher_id}:{current_page}'
        ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "Back"),
        callback_data=f'admin_voucher_list:{current_page}'
    ))
    return keyboard.as_markup()


def back_in_admin_vouchers_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f"admin_vouchers"),],
    ])


def back_in_start_creating_admin_vouchers_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "In start"), callback_data=f"admin_create_voucher"),],
    ])


