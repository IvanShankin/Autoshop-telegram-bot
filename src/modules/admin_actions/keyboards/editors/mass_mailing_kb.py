from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.admins.actions.actions_admin import get_sent_mass_messages_by_page, get_count_sent_messages
from src.services.database.admins.models import SentMasMessages
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.utils.i18n import get_text


def admin_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","Editor"), callback_data=f"editor_mes_mailing"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","History"), callback_data=f"sent_message_list:1"),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f"editors"),]

    ])


def editor_message_mailing_kb(language: str, button_url: str | None = None):
    keyboard = InlineKeyboardBuilder()

    if button_url:
        keyboard.row(InlineKeyboardButton(text="Open", url=button_url))
        keyboard.row(InlineKeyboardButton(text=get_config().app.solid_line, callback_data="none"))

    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "Start mailing"), callback_data=f"confirm_start_mailing"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "Change Photo"), callback_data=f"change_mailing_photo"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "Change text"), callback_data=f"change_mailing_text"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "Change button url"), callback_data=f"change_mailing_btn_url"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f"admin_mailing"))

    return keyboard.as_markup()


def confirm_start_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general","Confirm"), callback_data=f'start_mass_mailing'),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editor_mes_mailing'),]
    ])


def change_mailing_photo_kb(language: str, current_show_image: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "{indicator} Show").format(indicator='🟢' if current_show_image else '🔴'),
            callback_data=f'update_show_mailing_image:{int(not current_show_image)}'
        )],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editor_mes_mailing'),]
    ])


def change_mailing_text_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","Hints to the text"), callback_data=f'open_mailing_tip'),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editor_mes_mailing'),]
    ])


def change_mailing_btn_url_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_general',"Delete"), callback_data=f'delete_mailing_btn_url'),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editor_mes_mailing'),]
    ])


async def all_admin_mass_mailing_kb(language: str, current_page: int):
    """Клавиатура со списком только активных ваучеров у администрации"""
    records = await get_sent_mass_messages_by_page(page=current_page, page_size=get_config().different.page_size)
    total = await get_count_sent_messages()
    total_pages = max(ceil(total / get_config().different.page_size), 1)

    def item_button(sent_message: SentMasMessages):
        return InlineKeyboardButton(
            text=sent_message.created_at.strftime(get_config().different.dt_format),
            callback_data=f"show_sent_mass_message:{current_page}:{sent_message.message_id}"
        )

    return pagination_keyboard(
        records,
        current_page,
        total_pages,
        item_button,
        left_prefix=f"sent_message_list",
        right_prefix=f"sent_message_list",
        back_text=get_text(language, "kb_general", "Back"),
        back_callback="admin_mailing",
    )


def show_sent_mass_message_kb(language: str, current_page: int, message_id: int, button_url: str | None = None):
    keyboard = InlineKeyboardBuilder()

    if button_url:
        keyboard.row(InlineKeyboardButton(text="Open", url=button_url))
        keyboard.row(InlineKeyboardButton(text=get_config().app.solid_line, callback_data="none"))

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel",'Detail'),
        callback_data=f'detail_mass_msg:{current_page}:{message_id}'
    ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "Back"),
        callback_data=f'sent_message_list:{current_page}'
    ))

    return keyboard.as_markup()


def back_in_show_sent_mass_message_kb(language: str, current_page: int, message_id: int, button_url: str | None = None):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'show_sent_mass_message:{current_page}:{message_id}'
        ), ]
    ])


def back_in_change_mailing_text_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'change_mailing_text'),]
    ])


def back_in_editor_mes_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'editor_mes_mailing'),]
    ])


def back_in_admin_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'admin_mailing'),]
    ])