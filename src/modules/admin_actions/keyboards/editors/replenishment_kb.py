from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.services.database.system.actions.actions import get_all_types_payments
from src.utils.i18n import get_text

async def edit_type_payments_list_kb(language: str):
    type_payments = await get_all_types_payments()

    keyboard = InlineKeyboardBuilder()
    for type_payment in type_payments:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", type_payment.name_for_admin),
                callback_data=f'edit_type_payment:{type_payment.type_payment_id}'
            )
        )
    keyboard.row(
        InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editors')
    )
    return keyboard.as_markup()


async def edit_type_payment_kb(language: str, type_payment_id: int, current_index: int, current_show: bool):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "Rename"),
        callback_data=f'type_payment_rename:{type_payment_id}'
    ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", '{indicator} Show').format(indicator='🟢' if current_show else '🔴'),
        callback_data=f'type_payment_update_show:{type_payment_id}:{0 if current_show else 1}'
    ))
    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'Up index'),
            callback_data=f'type_payment_update_index:{type_payment_id}:{current_index + 1}'
        ),
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'Down index'),
            callback_data=f'type_payment_update_index:{type_payment_id}:{current_index - 1}'
        )
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "Edit commission"),
        callback_data=f'type_payment_update_commission:{type_payment_id}'
    ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "Back"),
        callback_data=f'replenishment_editor'
    ))
    return keyboard.as_markup()


def back_in_edit_type_payment_kb(language: str, type_payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"edit_type_payment:{type_payment_id}"
        )],
    ])
