from math import ceil

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.application.keyboards.keyboard_with_pages import pagination_keyboard
from src.application.models.modules import ProfileModule
from src.infrastructure.translations import get_text


def balance_transfer_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "transfer_by_id"), callback_data='transfer_money')],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "create_voucher"), callback_data='create_voucher')],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "my_vouchers"), callback_data=f'voucher_list:{user_id}:1')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'profile')],
    ])


def confirmation_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data='confirm_transfer_money',
            style="success",
        ),
         InlineKeyboardButton(
            text=get_text(language, "kb_general", "again"),
            callback_data='transfer_money',
            style="primary",
         )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'balance_transfer',
            style="danger",
        )],
    ])


def confirmation_voucher_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data='confirm_create_voucher',
            style="success",
        ),
         InlineKeyboardButton(
            text=get_text(language, "kb_general", "again"),
            callback_data='create_voucher',
            style="primary",
         )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'balance_transfer',
            style="danger",
        )],
    ])


def back_in_balance_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'balance_transfer')],
    ])


def replenishment_and_back_in_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "top_up_balance"), callback_data='show_type_replenishment')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data='balance_transfer')]
    ])


async def all_vouchers_kb(
    current_page: int,
    target_user_id: int,
    user_id: int,
    language: str,
    profile_module: ProfileModule
):
    """Клавиатура со списком только активных ваучеров у данного пользователя"""
    records = await profile_module.voucher_service.get_valid_voucher_by_page(
        target_user_id, current_page, profile_module.conf.different.page_size
    )
    total = await profile_module.voucher_service.get_count_voucher(target_user_id)
    total_pages = max(ceil(total / profile_module.conf.different.page_size), 1)

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
        back_text=get_text(language, "kb_general", "back"),
        back_callback="balance_transfer" if target_user_id == user_id else f"user_management:{target_user_id}",
    )


def show_voucher_kb(language: str, current_page: int, target_user_id: int, user_id: int, voucher_id: int):
    keyboard = InlineKeyboardBuilder()
    if target_user_id == user_id:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_profile", 'deactivate'),
                callback_data=f'confirm_deactivate_voucher:{voucher_id}:{current_page}'
            ),
        )

    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        ),
    )
    return keyboard.as_markup()


def confirm_deactivate_voucher_kb(language: str, current_page: int, target_user_id: int, voucher_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data=f'deactivate_voucher:{voucher_id}:{current_page}',
            style="success",
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}',
            style="danger",
        )]
    ])


def back_in_all_voucher_kb(language: str, current_page: int, target_user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        )]
    ])