from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


def _data_by_id_page_1(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Users"),
            callback_data=f"get_id_or_user_user_management"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Replenishment"),
            callback_data=f"replenishment_by_id:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Purchase account"),
            callback_data=f"purchase_account_by_id:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Sold Account"),
            callback_data=f"sold_account_by_id:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Vouchers"),
            callback_data=f"voucher_by_id:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Activate voucher"),
            callback_data=f"activate_voucher_by_id:1"
        )],

        # переходы
        [
            InlineKeyboardButton(text="⬅️",callback_data=f"none"),
            InlineKeyboardButton(text="1/2",callback_data=f"none"),
            InlineKeyboardButton(text="➡️", callback_data=f"data_by_id:2")
        ],

        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"admin_panel"
        )],

    ])


def _data_by_id_page_2(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Promo code"),
            callback_data=f"promo_code_by_id:2"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Promo code activation"),
            callback_data=f"promo_code_activation_by_id:2"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Referral"),
            callback_data=f"referral_by_id:2"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Income from referral"),
            callback_data=f"income_from_ref_by_id:2"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Transfer money"),
            callback_data=f"transfer_money_by_id:2"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Wallet transfer"),
            callback_data=f"wallet_transaction_by_id:2"
        )],


        # переходы
        [
            InlineKeyboardButton(text="⬅️", callback_data=f"data_by_id:1"),
            InlineKeyboardButton(text="2/2", callback_data=f"none"),
            InlineKeyboardButton(text="➡️", callback_data=f"none")
        ],


        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"admin_panel"
        )],

    ])


def data_by_id_by_page_kb(language: str, current_page: int):
    if current_page == 1:
        return _data_by_id_page_1(language)
    else:
        return _data_by_id_page_2(language)


def back_in_show_data_by_id_kb(language: str, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'data_by_id:{current_page}'
        )]
    ])