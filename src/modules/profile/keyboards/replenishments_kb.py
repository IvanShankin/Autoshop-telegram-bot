from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.services.database.system.actions.actions import get_all_types_payments
from src.utils.i18n import get_text


async def type_replenishment_kb(language: str):
    type_payments = await get_all_types_payments()
    keyboard = InlineKeyboardBuilder()

    for type_payment in type_payments:
        if type_payment.is_active:
            keyboard.row(InlineKeyboardButton(
                text=type_payment.name_for_user,
                callback_data=f'replenishment:{type_payment.type_payment_id}:{type_payment.name_for_user}')
            )

    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='profile'))
    keyboard.adjust(1)
    return keyboard.as_markup()


def payment_invoice(language: str, url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_general', 'Pay'), url=url)],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='show_type_replenishment')]
    ])


def back_in_type_replenishment_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='show_type_replenishment')]
        ])