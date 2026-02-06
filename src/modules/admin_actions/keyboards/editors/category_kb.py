from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.categories.actions import get_categories
from src.services.database.categories.models import CategoryFull
from src.services.database.categories.models import ProductType, Categories, UniversalMediaType, AccountServiceType
from src.utils.i18n import get_text


async def show_main_categories_kb(language: str,):
    categories = await get_categories(language=language, return_not_show = True)
    keyboard = InlineKeyboardBuilder()

    for cat in categories:
        keyboard.row(InlineKeyboardButton(text=str(cat.name), callback_data=f"show_category_admin:{cat.category_id}"))

    keyboard.row(InlineKeyboardButton(text=get_config().app.solid_line, callback_data=f'none'))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "add_category"),
        callback_data=f'add_category:None')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
        callback_data=f'editors')
    )
    return keyboard.as_markup()


def back_in_category_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'category_editor')]
    ])


def in_category_editor_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "in_category_editor"),
            callback_data=f'category_editor'
        )]
    ])


async def show_category_admin_kb(
    language: str,
    category_id: int,
    category: Categories | CategoryFull,
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
        text=get_text(language, "kb_admin_panel", "add_subcategory"),
        callback_data=f'add_category:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", f"{"remove_storage" if category.is_product_storage else "make_storage"}"),
        callback_data=f'category_update_storage:{category_id}:{0 if category.is_product_storage else 1}')
    )

    if category.is_product_storage:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "delete_all_products"),
            callback_data=f'confirm_del_all_products:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "unload_all_products"),
            callback_data=f'category_upload_products:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "load_products"),
            callback_data=f'category_load_products:{category_id}')
        )

    # индексы
    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'up_index'),
            callback_data=f'category_update_index:{category_id}:{category.index + 1}'
        ),
        InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'down_index'),
            callback_data=f'category_update_index:{category_id}:{category.index - 1}'
        )
    )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "show_indicator").format(indicator='🟢' if category.show else '🔴'),
        callback_data=f'category_update_show:{category_id}:{0 if category.show else 1}'
    ))

    if category.product_type == ProductType.UNIVERSAL:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "multiple_sale_indicator").format(indicator='🟢' if category.reuse_product else '🔴'),
            callback_data=f'category_update_reuse_product:{category_id}:{0 if category.reuse_product else 1}'
        ))

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "wholesale_purchase_indicator").format(indicator='🟢' if category.allow_multiple_purchase else '🔴'),
        callback_data=f'category_update_multiple_purchase:{category_id}:{0 if category.allow_multiple_purchase else 1}'
    ))
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", 'update_data'),
        callback_data=f'category_update_data:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "delete"),
        callback_data=f'category_confirm_delete:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
        callback_data=f'category_editor' if category.is_main else f'show_category_admin:{category.parent_id}')
    )
    return keyboard.as_markup()


def change_category_data_kb(language: str, category_id: int, is_product_storage: bool, show_default: bool):
    keyboard = InlineKeyboardBuilder()

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", 'name_description'),
        callback_data=f'category_update_name_or_des:{category_id}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(
            language,
            "kb_admin_panel",
            "show_by_default_indicator"
        ).format(indicator='🟢' if show_default else '🔴'),
        callback_data=f'update_show_ui_default_category:{category_id}:{1 if show_default else 0}')
    )
    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", 'image'),
        callback_data=f'category_update_image:{category_id}')
    )

    if is_product_storage:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "price_one_product"),
            callback_data=f'category_update_price:{category_id}')
        )
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "cost_price_one_product"),
            callback_data=f'category_update_cost_price:{category_id}')
        )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_admin_panel", "number_button_in_row"),
        callback_data=f'category_update_number_button:{category_id}')
    )


    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
        callback_data=f'show_category_admin:{category_id}')
    )

    return keyboard.as_markup()


def select_product_type(language: str, category_id: int):
    keyboard = InlineKeyboardBuilder()
    for product_type in ProductType:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_profile", product_type.value),
                callback_data=f'choice_product_type:{category_id}:{product_type.value}'
            )
        )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
        callback_data=f'show_category_admin:{category_id}')
    )

    return keyboard.as_markup()


def select_account_service_type(language: str, category_id: int):
    keyboard = InlineKeyboardBuilder()
    for account_service in AccountServiceType:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_profile", account_service.value),
                callback_data=f'choice_account_service:{category_id}:{account_service.value}'
            )
        )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
        callback_data=f'show_category_admin:{category_id}')
    )

    return keyboard.as_markup()


def select_universal_media_type(language: str, category_id: int):
    keyboard = InlineKeyboardBuilder()
    for media in UniversalMediaType:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "universal_media_type", media.value),
                callback_data=f'choice_universal_media_type:{category_id}:{media.value}'
            )
        )

    keyboard.row(InlineKeyboardButton(
        text=get_text(language, "kb_general", "back"),
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
            text=get_text(language, "kb_admin_panel", "name"),
            callback_data=f'category_update_name:{category_id}:{lang}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", 'description'),
            callback_data=f'category_update_descr:{category_id}:{lang}'
        )]
    ])


def delete_product_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data=f'delete_all_products:{category_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'show_category_admin:{category_id}'
        )]
    ])


def delete_category_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data=f'delete_category:{category_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'show_category_admin:{category_id}'
        )]
    ])



def _get_example_import_kb(language: str, category_id: int, callback_data: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", "get_example"),
                callback_data=callback_data
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text(language, "kb_general", "back"),
                callback_data=f'show_category_admin:{category_id}'
            )
        ]
    ])


def get_example_import_tg_acc_kb(language: str, category_id: int):
    return _get_example_import_kb(language, category_id, f"get_example_import_tg_acc")


def get_example_import_other_acc_kb(language: str, category_id: int):
    return _get_example_import_kb(language, category_id, f"get_example_import_other_acc")


def get_example_import_product_kb(language: str, category_id: int):
    return _get_example_import_kb(language, category_id, f"get_example_import_universals")


def back_in_category_update_data_kb(language: str, category_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "to_the_data"),
            callback_data=f'category_update_data:{category_id}'
        )]
    ])


def back_in_category_kb(language: str, category_id: int, i18n_key: str = "back"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general",i18n_key), callback_data=f'show_category_admin:{category_id}')]
    ])