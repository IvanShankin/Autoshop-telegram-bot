from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import ALLOWED_LANGS
from src.services.database.selling_accounts.actions import get_all_account_services, get_all_types_account_service, \
    get_account_categories_by_parent_id
from src.utils.i18n import get_text

SOLID_LINE = '―――――――――――――――――――――――――――'


async def main_admin_kb(language: str):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=get_text(language, 'keyboard','Category Editor'), callback_data="category_editor"))
    keyboard.adjust(1)
    return keyboard.as_markup()

# ================ СЕРВИСЫ ================

async def all_services_account_admin_kb(language: str):
    services = await get_all_account_services(return_not_show = True)
    keyboard = InlineKeyboardBuilder()

    for ser in services:
        keyboard.add(InlineKeyboardButton(text=str(ser.name), callback_data=f'show_service_acc_admin:{ser.account_service_id}'))

    keyboard.add(InlineKeyboardButton(text=SOLID_LINE, callback_data='none'))
    keyboard.add(InlineKeyboardButton(text=get_text(language, 'keyboard','Add'), callback_data=f'add_account_service'))
    keyboard.add(InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'admin_panel'))
    keyboard.adjust(1)
    return keyboard.as_markup()


async def show_service_acc_admin_kb(language: str, current_show: bool, current_index: int, service_id: int):
    categories = await get_account_categories_by_parent_id(account_service_id=service_id, return_not_show = True)
    keyboard = InlineKeyboardBuilder()

    for cat in categories:
        keyboard.row(
            InlineKeyboardButton(text=str(cat.name), callback_data=f'show_acc_category_admin:{cat.account_category_id}'))

    keyboard.row(InlineKeyboardButton(text=SOLID_LINE, callback_data='none'))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard',"Add Category"),
        callback_data=f'add_main_acc_category:{service_id}')
    )
    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, 'keyboard','Up index'),
            callback_data=f'service_update_index:{service_id}:{current_index + 1}'
        ),
        InlineKeyboardButton(
            text=get_text(language, 'keyboard','Down index'),
            callback_data=f'service_update_index:{service_id}:{current_index - 1}'
        )
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard','{indicator} Show').format(indicator= '🟢' if current_show else '🔴'),
        callback_data=f'service_update_show:{service_id}:{0 if current_show else 1}'
    ))
    keyboard.row(InlineKeyboardButton(text=get_text(language, 'keyboard','Rename'), callback_data=f'service_rename:{service_id}'))
    keyboard.row(InlineKeyboardButton(text=get_text(language, 'keyboard','Delete'), callback_data=f'service_confirm_delete:{service_id}'))
    keyboard.row(InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'category_editor'))
    return keyboard.as_markup()


async def all_services_types_kb(language: str):
    all_types_service = await get_all_types_account_service()
    keyboard = InlineKeyboardBuilder()

    for type_service in all_types_service:
        keyboard.add(InlineKeyboardButton(
            text=type_service.name,
            callback_data=f'select_type_service:{type_service.type_account_service_id}')
        )

    keyboard.add(InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'category_editor'))
    keyboard.adjust(1)
    return keyboard.as_markup()


def to_services_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard','To services'), callback_data=f'category_editor'),]
    ])


def delete_service_kb(language: str, account_service_id: int):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text=get_text(language, 'keyboard','Confirm'), callback_data=f'delete_acc_service:{account_service_id}'),
        InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'show_service_acc_admin:{account_service_id}')
    )
    return keyboard.as_markup()


def back_in_service_kb(language: str, service_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard','Back'), callback_data=f'show_service_acc_admin:{service_id}')]
    ])


# ================ Категории ================

async def show_account_category_admin_kb(
    language: str,
    current_show: bool,
    current_index: int,
    service_id: int,
    category_id: int,
    parent_category_id: int | None,
    is_main: bool,
    is_account_storage: bool
):
    categories = await get_account_categories_by_parent_id(
        account_service_id=service_id,
        parent_id=category_id,
        return_not_show=True
    )
    keyboard = InlineKeyboardBuilder()

    for cat in categories:
        keyboard.row(InlineKeyboardButton(text=str(cat.name), callback_data=f'show_acc_category_admin:{cat.account_category_id}'))

    keyboard.row(InlineKeyboardButton(text=SOLID_LINE, callback_data='none'))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', "Add subcategory"),
        callback_data=f'add_acc_category:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', f"{"Remove storage" if is_account_storage else "Make storage"}"),
        callback_data=f'acc_category_update_storage:{category_id}:{0 if is_account_storage else 1}')
    )

    if is_account_storage:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Delete all accounts"),
            callback_data=f'acc_category_del_all_acc:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Unload all accounts"),
            callback_data=f'acc_category_upload_acc:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Load accounts"),
            callback_data=f'acc_category_load_acc:{category_id}')
        )

    # индексы
    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Up index'),
            callback_data=f'acc_category_update_index:{category_id}:{current_index + 1}'
        ),
        InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Down index'),
            callback_data=f'acc_category_update_index:{category_id}:{current_index - 1}'
        )
    )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', '{indicator} Show').format(indicator='🟢' if current_show else '🔴'),
        callback_data=f'acc_category_update_show:{category_id}:{0 if current_show else 1}'
    ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', 'Update data'),
        callback_data=f'category_update_data:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', 'Delete'),
        callback_data=f'acc_category_confirm_delete:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', 'Back'),
        callback_data=f'show_service_acc_admin:{service_id}' if is_main else f'show_acc_category_admin:{parent_category_id}')
    )
    return keyboard.as_markup()


def change_category_data_kb(language: str, category_id: int, is_account_storage: bool, show_default: bool):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', 'Name / Description'),
        callback_data=f'acc_category_update_name_or_des:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(
            language,
            'keyboard',
            "{indicator} Show by default"
        ).format(indicator='🟢' if show_default else '🔴'),
        callback_data=f'update_show_ui_default_category:{category_id}:{1 if show_default else 0}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', 'Image'),
        callback_data=f'acc_category_update_image:{category_id}')
    )

    if is_account_storage:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Price one account'),
            callback_data=f'acc_category_update_price:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Cost Price one account'),
            callback_data=f'acc_category_update_cost_price:{category_id}')
        )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', 'Number button in row'),
        callback_data=f'acc_category_update_number_button:{category_id}')
    )


    keyboard.row(InlineKeyboardButton(
        text=get_text(language, 'keyboard', 'Back'),
        callback_data=f'show_acc_category_admin:{category_id}')
    )

    return keyboard.as_markup()


def select_lang_category_kb(language: str, category_id: int):
    keyboard = InlineKeyboardBuilder()
    for lang in ALLOWED_LANGS:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, 'keyboard', lang),
                callback_data=f'choice_lang_category_data:{category_id}:{lang}'
            )
        )
    return keyboard.as_markup()


def name_or_description_kb(language: str, category_id: int, lang: str):
    """
    :param lang: Код языка из переменной ALLOWED_LANGS
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Name"),
            callback_data=f'acc_category_update_name:{category_id}:{lang}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Description'),
            callback_data=f'acc_category_update_descr:{category_id}:{lang}'
        )]
    ])


def delete_category_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Confirm'),
            callback_data=f'delete_acc_category:{category_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f'show_acc_category_admin:{category_id}'
        )]
    ])


def back_in_category_update_data_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "To the data"),
            callback_data=f'category_update_data:{category_id}'
        )]
    ])


def back_in_category_kb(language: str, category_id: int, i18n_key: str = "Back"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'keyboard',i18n_key), callback_data=f'show_acc_category_admin:{category_id}')]
    ])