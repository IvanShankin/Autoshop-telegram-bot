from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.i18n import get_text


def choice_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel",'Categories'), callback_data=f'category_editor'),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","Services replenishments"), callback_data=f'replenishment_editor'),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel",'Images'), callback_data=f'images_editor_list:1'),],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile',"Referral system"), callback_data=f"lvl_list_ref_system"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","Vouchers"), callback_data=f"admin_vouchers"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","Promo codes"), callback_data=f"admin_promo"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","Mailing"), callback_data=f"admin_mailing"),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'admin_panel'),]
    ])

def back_in_choice_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editors'),]
    ])