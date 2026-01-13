from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.categories.actions import get_categories
from src.utils.i18n import get_text


async def show_main_categories_kb(language: str,):
    categories = await get_categories(language=language, return_not_show = True)
    keyboard = InlineKeyboardBuilder()

    for cat in categories:
        keyboard.row(InlineKeyboardButton(text=str(cat.name), callback_data=f'show_main_categories'))

    keyboard.row(InlineKeyboardButton(text=get_config().app.solid_line, callback_data=f'none'))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "Add subcategory"),
        callback_data=f'add_category:None')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "Back"),
        callback_data=f'editors')
    )
    return keyboard.as_markup()


async def show_category_admin_kb(
    language: str,
    current_show: bool,
    current_index: int,
    category_id: int,
    parent_category_id: int | None,
    is_main: bool,
    is_product_storage: bool
):
    categories = await get_categories(
        parent_id=category_id,
        return_not_show=True
    )
    keyboard = InlineKeyboardBuilder()

    for cat in categories:
        keyboard.row(InlineKeyboardButton(text=str(cat.name), callback_data=f'show_category_admin:{cat.category_id}'))

    keyboard.row(InlineKeyboardButton(text=get_config().app.solid_line, callback_data='none'))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "Add subcategory"),
        callback_data=f'add_category:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", f"{"Remove storage" if is_product_storage else "Make storage"}"),
        callback_data=f'category_update_storage:{category_id}:{0 if is_product_storage else 1}')
    )

    if is_product_storage:
        
        # КАК ДОЛЖНО БЫТЬ: КАКОЕ-ТО ДЕЙСТВИЕ ПОСЫЛАЕТСЯ В HANDLER И ИМЕННО ОН РЕШАЕТ, ЧТО И КАК ДЕЛАТЬ.
        # КАК ДОЛЖНО БЫТЬ: КАКОЕ-ТО ДЕЙСТВИЕ ПОСЫЛАЕТСЯ В HANDLER И ИМЕННО ОН РЕШАЕТ, ЧТО И КАК ДЕЛАТЬ.
        # КАК ДОЛЖНО БЫТЬ: КАКОЕ-ТО ДЕЙСТВИЕ ПОСЫЛАЕТСЯ В HANDLER И ИМЕННО ОН РЕШАЕТ, ЧТО И КАК ДЕЛАТЬ.
        # КАК ДОЛЖНО БЫТЬ: КАКОЕ-ТО ДЕЙСТВИЕ ПОСЫЛАЕТСЯ В HANDLER И ИМЕННО ОН РЕШАЕТ, ЧТО И КАК ДЕЛАТЬ.
        
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Delete all accounts"),
            callback_data=f'confirm_del_all_products:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Unload all accounts"),
            callback_data=f'category_upload_products:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Load accounts"),
            callback_data=f'category_load_products:{category_id}')
        )

    # индексы
    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'Up index'),
            callback_data=f'category_update_index:{category_id}:{current_index + 1}'
        ),
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'Down index'),
            callback_data=f'category_update_index:{category_id}:{current_index - 1}'
        )
    )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", '{indicator} Show').format(indicator='🟢' if current_show else '🔴'),
        callback_data=f'category_update_show:{category_id}:{0 if current_show else 1}'
    ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", 'Update data'),
        callback_data=f'category_update_data:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "Delete"),
        callback_data=f'category_confirm_delete:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "Back"),
        callback_data=f'category_editor' if is_main else f'show_category_admin:{parent_category_id}')
    )
    return keyboard.as_markup()


def change_category_data_kb(language: str, category_id: int, is_account_storage: bool, show_default: bool):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", 'Name / Description'),
        callback_data=f'category_update_name_or_des:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(
            language,
            "kb_admin_panel",
            "{indicator} Show by default"
        ).format(indicator='🟢' if show_default else '🔴'),
        callback_data=f'update_show_ui_default_category:{category_id}:{1 if show_default else 0}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", 'Image'),
        callback_data=f'category_update_image:{category_id}')
    )

    if is_account_storage:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'Price one account'),
            callback_data=f'category_update_price:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'Cost Price one account'),
            callback_data=f'category_update_cost_price:{category_id}')
        )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", 'Number button in row'),
        callback_data=f'category_update_number_button:{category_id}')
    )


    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "Back"),
        callback_data=f'show_category_admin:{category_id}')
    )

    return keyboard.as_markup()


def select_lang_category_kb(language: str, category_id: int):
    keyboard = InlineKeyboardBuilder()
    for lang in get_config().app.allowed_langs:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", lang),
                callback_data=f'choice_lang_category_data:{category_id}:{lang}'
            )
        )
    return keyboard.as_markup()


def name_or_description_kb(language: str, category_id: int, lang: str):
    """
    :param lang: Код языка из переменной get_config().app.allowed_langs
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "Name"),
            callback_data=f'category_update_name:{category_id}:{lang}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'Description'),
            callback_data=f'category_update_descr:{category_id}:{lang}'
        )]
    ])


def delete_product_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Confirm"),
            callback_data=f'delete_all_products:{category_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'show_category_admin:{category_id}'
        )]
    ])


def delete_category_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Confirm"),
            callback_data=f'delete_category:{category_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'show_category_admin:{category_id}'
        )]
    ])


def back_in_category_update_data_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "To the data"),
            callback_data=f'category_update_data:{category_id}'
        )]
    ])


def back_in_category_kb(language: str, category_id: int, i18n_key: str = "Back"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_general',i18n_key), callback_data=f'show_category_admin:{category_id}')]
    ])