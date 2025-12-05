from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.i18n import get_text


def choice_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Services and Categories'), callback_data=f'services_editor'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"Services replenishments"), callback_data=f'replenishment_editor'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Images'), callback_data=f'images_editor_list:1'),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"Referral system"), callback_data=f"lvl_list_ref_system"),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"Vouchers"), callback_data=f"admin_vouchers"),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard',"Promo Codes"), callback_data=f"admin_promo_code"),],
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'admin_panel'),]
    ])

def back_in_choice_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'editors'),]
    ])