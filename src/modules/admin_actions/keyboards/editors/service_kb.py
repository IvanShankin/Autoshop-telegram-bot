from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.product_categories.actions import get_all_account_services, get_all_types_account_service, \
    get_account_categories_by_parent_id
from src.utils.i18n import get_text



async def all_services_account_admin_kb(language: str):
    services = await get_all_account_services(return_not_show = True)
    keyboard = InlineKeyboardBuilder()

    for ser in services:
        keyboard.add(InlineKeyboardButton(text=str(ser.name), callback_data=f'show_service_acc_admin:{ser.account_service_id}'))

    keyboard.add(InlineKeyboardButton(text=get_config().app.solid_line, callback_data='none'))
    keyboard.add(InlineKeyboardButton(text=get_text(language, "kb_admin_panel",'Add'), callback_data=f'add_account_service'))
    keyboard.add(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'admin_panel'))
    keyboard.adjust(1)
    return keyboard.as_markup()


async def show_service_acc_admin_kb(language: str, current_show: bool, current_index: int, service_id: int):
    categories = await get_account_categories_by_parent_id(account_service_id=service_id, return_not_show = True)
    keyboard = InlineKeyboardBuilder()

    for cat in categories:
        keyboard.row(
            InlineKeyboardButton(text=str(cat.name), callback_data=f'show_acc_category_admin:{cat.category_id}'))

    keyboard.row(InlineKeyboardButton(text=get_config().app.solid_line, callback_data='none'))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel","Add Category"),
        callback_data=f'add_main_acc_category:{service_id}')
    )
    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel",'Up index'),
            callback_data=f'service_update_index:{service_id}:{current_index + 1}'
        ),
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel",'Down index'),
            callback_data=f'service_update_index:{service_id}:{current_index - 1}'
        )
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel",'{indicator} Show').format(indicator= '🟢' if current_show else '🔴'),
        callback_data=f'service_update_show:{service_id}:{0 if current_show else 1}'
    ))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_admin_panel",'Rename'), callback_data=f'service_rename:{service_id}'))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general","Delete"), callback_data=f'service_confirm_delete:{service_id}'))
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'services_editor'))
    return keyboard.as_markup()


async def all_services_types_kb(language: str):
    all_types_service = await get_all_types_account_service()
    keyboard = InlineKeyboardBuilder()

    for type_service in all_types_service:
        keyboard.add(InlineKeyboardButton(
            text=type_service.name,
            callback_data=f'select_type_service:{type_service.type_account_service_id}')
        )

    keyboard.add(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'services_editor'))
    keyboard.adjust(1)
    return keyboard.as_markup()


def to_services_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_admin_panel",'To services'), callback_data=f'services_editor'),]
    ])


def delete_service_kb(language: str, account_service_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text=get_text(language, "kb_general", "Confirm"), callback_data=f'delete_acc_service:{account_service_id}'),
        InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'show_service_acc_admin:{account_service_id}')
    )
    return keyboard.as_markup()


def back_in_service_kb(language: str, service_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'show_service_acc_admin:{service_id}')]
    ])


def back_in_all_type_service_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'add_account_service')]
    ])
