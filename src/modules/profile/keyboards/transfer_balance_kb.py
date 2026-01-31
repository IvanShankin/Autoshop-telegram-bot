from math import ceil

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.discounts.actions import get_count_voucher
from src.services.database.discounts.actions import get_valid_voucher_by_page
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.utils.i18n import get_text


def balance_transfer_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Transfer by id'), callback_data='transfer_money')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Create voucher'), callback_data='create_voucher')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'My vouchers'), callback_data=f'voucher_list:{user_id}:1')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'profile')],
    ])


def confirmation_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Confirm"), callback_data='confirm_transfer_money'),
         InlineKeyboardButton(text=get_text(language, "kb_general", "Again"), callback_data='transfer_money')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'balance_transfer')],
    ])


def confirmation_voucher_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Confirm"), callback_data='confirm_create_voucher'),
         InlineKeyboardButton(text=get_text(language, "kb_general", "Again"), callback_data='create_voucher')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'balance_transfer')],
    ])


def back_in_balance_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'balance_transfer')],
    ])


def replenishment_and_back_in_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Top up your balance'), callback_data='show_type_replenishment')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='balance_transfer')]
    ])


async def all_vouchers_kb(current_page: int, target_user_id: int, user_id: int, language: str):
    """Клавиатура со списком только активных ваучеров у данного пользователя"""
    records = await get_valid_voucher_by_page(target_user_id, current_page, get_config().different.page_size)
    total = await get_count_voucher(target_user_id)
    total_pages = max(ceil(total / get_config().different.page_size), 1)

    def item_button(voucher):
        return InlineKeyboardButton(
            text=f"{voucher.amount} ₽   {voucher.activation_code}",
            callback_data=f"show_voucher:{target_user_id}:{current_page}:{voucher.voucher_id}"
        )

    return pagination_keyboard(
        records,
        current_page,
        total_pages,
        item_button,
        left_prefix=f"voucher_list:{target_user_id}",
        right_prefix=f"voucher_list:{target_user_id}",
        back_text=get_text(language, "kb_general", "Back"),
        back_callback="transfer_money" if target_user_id == user_id else f"user_management:{target_user_id}",
    )


def show_voucher_kb(language: str, current_page: int, target_user_id: int, user_id: int, voucher_id: int):
    keyboard = InlineKeyboardBuilder()
    if target_user_id == user_id:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, 'kb_profile', 'Deactivate'),
                callback_data=f'confirm_deactivate_voucher:{voucher_id}:{current_page}'
            ),
        )

    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        ),
    )
    return keyboard.as_markup()


def confirm_deactivate_voucher_kb(language: str, current_page: int, target_user_id: int, voucher_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
                text=get_text(language, "kb_general", "Confirm"),
                callback_data=f'deactivate_voucher:{voucher_id}:{current_page}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        )]
    ])


def back_in_all_voucher_kb(language: str, current_page: int, target_user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        )]
    ])