from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.utils.i18n import get_text


def profile_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "top_up_balance"), callback_data="show_type_replenishment")],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "purchases"), callback_data="purchases")],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "balance_transfer"), callback_data="balance_transfer")],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "referral_system"), callback_data="referral_system")],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "history_transfer"), callback_data=f"transaction_list:{user_id}:1")],
        [InlineKeyboardButton(text=get_text(language, "kb_profile", "settings"), callback_data="profile_settings")]
    ])


def back_in_profile_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data="profile")]
    ])


