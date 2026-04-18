from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.application.models.modules import AdminModule
from src.database.models.admins import SentMasMessages
from src.application.keyboards.keyboard_with_pages import pagination_keyboard
from src.infrastructure.translations import get_text


def admin_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","editor"), callback_data=f"editor_mes_mailing"),],
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","history"), callback_data=f"sent_message_list:1"),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f"editors"),]

    ])


def editor_message_mailing_kb(language: str, admin_module: AdminModule, button_url: str | None = None, ):
    keyboard = InlineKeyboardBuilder()

    if button_url:
        keyboard.row(InlineKeyboardButton(text="Open", url=button_url))
        keyboard.row(InlineKeyboardButton(text=admin_module.conf.app.solid_line, callback_data="none"))

    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "start_mailing"), callback_data=f"confirm_start_mailing"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "change_photo"), callback_data=f"change_mailing_photo"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "change_text"), callback_data=f"change_mailing_text"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel", "change_button_url"), callback_data=f"change_mailing_btn_url"))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f"admin_mailing"))

    return keyboard.as_markup()


def confirm_start_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general","confirm"), callback_data=f'start_mass_mailing'),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'editor_mes_mailing'),]
    ])


def change_mailing_photo_kb(language: str, current_show_image: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "show_indicator").format(indicator='🟢' if current_show_image else '🔴'),
            callback_data=f'update_show_mailing_image:{int(not current_show_image)}'
        )],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'editor_mes_mailing'),]
    ])


def change_mailing_text_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel","hints_to_text"), callback_data=f'open_mailing_tip'),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'editor_mes_mailing'),]
    ])


def change_mailing_btn_url_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general","delete"), callback_data=f'delete_mailing_btn_url'),],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'editor_mes_mailing'),]
    ])


async def all_admin_mass_mailing_kb(language: str, current_page: int, admin_module: AdminModule,):
    """Клавиатура со списком только активных ваучеров у администрации"""
    records = await admin_module.sent_mass_message_service.get_msgs_by_page(
        page=current_page, page_size=admin_module.conf.different.page_size
    )
    total = await admin_module.sent_mass_message_service.get_count_msgs()
    total_pages = max(ceil(total / admin_module.conf.different.page_size), 1)

    def item_button(sent_message: SentMasMessages):
        return InlineKeyboardButton(
            text=sent_message.created_at.strftime(admin_module.conf.different.dt_format),
            callback_data=f"show_sent_mass_message:{current_page}:{sent_message.message_id}"
        )

    return pagination_keyboard(
        records,
        current_page,
        total_pages,
        item_button,
        left_prefix=f"sent_message_list",
        right_prefix=f"sent_message_list",
        back_text=get_text(language, "kb_general", "back"),
        back_callback="admin_mailing",
    )


def show_sent_mass_message_kb(
    language: str,
    current_page: int,
    message_id: int,
    admin_module: AdminModule,
    button_url: str | None = None
):
    keyboard = InlineKeyboardBuilder()

    if button_url:
        keyboard.row(InlineKeyboardButton(text="Open", url=button_url))
        keyboard.row(InlineKeyboardButton(text=admin_module.conf.app.solid_line, callback_data="none"))

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel",'detail'),
        callback_data=f'detail_mass_msg:{current_page}:{message_id}'
    ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
        callback_data=f'sent_message_list:{current_page}'
    ))

    return keyboard.as_markup()


def back_in_show_sent_mass_message_kb(language: str, current_page: int, message_id: int, button_url: str | None = None):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'show_sent_mass_message:{current_page}:{message_id}'
        ), ]
    ])


def back_in_change_mailing_text_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'change_mailing_text'),]
    ])


def back_in_editor_mes_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'editor_mes_mailing'),]
    ])


def back_in_admin_mailing_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'admin_mailing'),]
    ])