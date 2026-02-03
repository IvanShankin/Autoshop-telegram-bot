from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.utils.i18n import get_text


def profile_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Top up your balance'), callback_data='show_type_replenishment')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Purchases'), callback_data='purchases')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Balance transfer'), callback_data='balance_transfer')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Referral system'), callback_data='referral_system')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'History transfer'), callback_data=f'transaction_list:{user_id}:1')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Settings'), callback_data='profile_settings')]
    ])


def back_in_profile_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='profile')]
    ])


