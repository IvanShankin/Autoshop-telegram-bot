from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.i18n import get_text


def choice_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","categories"), callback_data=f'category_editor'),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","services_replenishments"), callback_data=f'replenishment_editor'),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel",'images'), callback_data=f'images_editor_list:1'),],
        [InlineKeyboardButton(text=get_text(language, "kb_profile","referral_system"), callback_data=f"lvl_list_ref_system"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","vouchers"), callback_data=f"admin_vouchers"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","promo_codes"), callback_data=f"admin_promo"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","mailing"), callback_data=f"admin_mailing"),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'admin_panel'),]
    ])

def back_in_choice_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'editors'),]
    ])