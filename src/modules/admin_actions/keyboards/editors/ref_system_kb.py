from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.referrals.actions import get_referral_lvl
from src.utils.i18n import get_text


async def lvl_list_ref_system_kb(language: str):
    ref_lvls = await get_referral_lvl()
    keyboard = InlineKeyboardBuilder()

    for lvl in ref_lvls:
        keyboard.row(InlineKeyboardButton(
            text=f"{lvl.level}   ―   {lvl.percent}%",
            callback_data=f'show_ref_lvl_editor:{lvl.referral_level_id}'
        ))

    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", get_config().app.solid_line), callback_data=f'none'))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel",'add'), callback_data=f'add_ref_lvl'))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'editors'))

    return keyboard.as_markup()


def ref_lvl_editor_kb(language: str, referral_level_id: int, is_first_lvl: bool):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "change_percent"),
        callback_data=f"change_persent_ref_lvl:{referral_level_id}")
    )

    if not is_first_lvl:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "change_achievement_amount"),
            callback_data=f"change_achievement_amount:{referral_level_id}"),
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_general", "delete"),
            callback_data=f"confirm_delete_ref_lvl:{referral_level_id}"),
        )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
        callback_data=f"lvl_list_ref_system"),
    )
    return keyboard.as_markup()


def confirm_del_lvl_kb(language: str, referral_level_id: int,):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data=f"delete_ref_lvl:{referral_level_id}"
        ),],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"show_ref_lvl_editor:{referral_level_id}"
        ),],
    ])


def back_in_lvl_list_ref_system_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f"lvl_list_ref_system"),]
    ])


def back_in_ref_lvl_editor_kb(language: str, referral_level_id: int, i18n_key = "back"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", i18n_key),
            callback_data=f"show_ref_lvl_editor:{referral_level_id}"
        ),]
    ])

