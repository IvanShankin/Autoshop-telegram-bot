from math import ceil
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.database.categories.actions import get_count_sold_account, \
    get_types_product_where_the_user_has_product, get_types_account_service_where_the_user_purchase
from src.services.database.categories.actions import get_sold_account_by_page
from src.services.database.categories.models import ProductType, AccountServiceType
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.utils.i18n import get_text, n_get_text
from src.utils.pars_number import e164_to_pretty


def in_purchased_account_kb(
    language: str,
    quantity_products: int,
    type_account_service: AccountServiceType,
    sold_account_id: Optional[int | None] = None
):
    """
    Используется при покупке аккаунтов
    :param sold_account_id: необходим только если приобретается один товар
    """

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=n_get_text(language, "kb_catalog", 'to_accounts', "to_accounts", quantity_products),
            callback_data=(
                f"sold_account:{sold_account_id}:{type_account_service.value}:1"
                if quantity_products == 1 and sold_account_id else
                f"all_sold_accounts:{type_account_service.value}:1"
            )
        )]
    ])


async def type_product_in_purchases_kb(language: str, user_id: int) -> InlineKeyboardMarkup:
    """Отобразит только те сервисы в которых у пользователя есть купленные товары"""

    type_products = await get_types_product_where_the_user_has_product(user_id)

    keyboard = InlineKeyboardBuilder()

    if ProductType.ACCOUNT in type_products:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_profile", ProductType.ACCOUNT.value),
            callback_data=f'services_sold_account')
        )

    if ProductType.UNIVERSAL in type_products:
        keyboard.row(InlineKeyboardButton(
            text=get_text(language, "kb_profile", ProductType.UNIVERSAL.value),
            callback_data=f'all_sold_universal:1')
        )
    # ПРИ ДОБАВЛЕНИЕ НОВЫХ ТОВАРОВ, РАСШИРИТЬ ПОИСК

    keyboard.row(
        InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f"profile"),
    )

    return keyboard.as_markup()


async def sold_account_type_service_kb(language: str, user_id: int) -> InlineKeyboardMarkup:
    types_accounts = await get_types_account_service_where_the_user_purchase(user_id)
    keyboard = InlineKeyboardBuilder()

    for account_type in types_accounts:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_profile", account_type.value),
                callback_data=f"all_sold_accounts:{account_type.value}:1"
            ),
        )

    keyboard.row(
        InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'purchases'),
    )
    return keyboard.as_markup()


async def sold_accounts_kb(
    language: str,
    current_page: int,
    type_account_service: AccountServiceType,
    user_id: int
):
    records = await get_sold_account_by_page(user_id, type_account_service, current_page, language, get_config().different.page_size)
    total = await get_count_sold_account(user_id, type_account_service)
    total_pages = max(ceil(total / get_config().different.page_size), 1)

    def item_button(acc):
        text = e164_to_pretty(acc.phone_number) if acc.phone_number else acc.name
        return InlineKeyboardButton(
            text=text,
            callback_data=f"sold_account:{acc.sold_account_id}:{type_account_service.value}:{current_page}"
        )

    return pagination_keyboard(
        records=records,
        current_page=current_page,
        total_pages=total_pages,
        item_button_func=item_button,
        left_prefix=f"all_sold_accounts:{type_account_service.value}",
        right_prefix=f"all_sold_accounts:{type_account_service.value}",
        back_text=get_text(language, "kb_general", "back"),
        back_callback="services_sold_account",
    )


def account_kb(
    language: str,
    sold_account_id: int,
    type_account_service: AccountServiceType,
    current_page: int,
    current_validity: bool
):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_profile", "login_details"),
            callback_data=f'login_details:{sold_account_id}:{type_account_service.value}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_profile", "check_for_validity"),
            # current_validity преобразовал в int что бы занимал меньше места
            callback_data=f'chek_valid_acc:{sold_account_id}:{type_account_service.value}:{current_page}:{int(current_validity)}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "delete"),
            callback_data=f'confirm_del_acc:{sold_account_id}:{type_account_service.value}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'all_sold_accounts:{type_account_service.value}:{current_page}')
        ]
    ])


def login_details_kb(
    language: str,
    sold_account_id: int,
    type_account_service: AccountServiceType,
    current_page: int,
    for_admin: bool = False
):
    keyboard = InlineKeyboardBuilder()
    if type_account_service == AccountServiceType.TELEGRAM:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_profile", "get_code"),
                callback_data=f'get_code_acc:{sold_account_id}'
            ),
        )
        keyboard.row(
            InlineKeyboardButton(
                text='tdata',
                callback_data=f'get_tdata_acc:{sold_account_id}'
            ),
        )
        keyboard.row(
            InlineKeyboardButton(
                text='.session',
                callback_data=f'get_session_acc:{sold_account_id}'
            ),
        )
    # в дальнейшем тут писать для других сервисов
    else:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, "kb_profile", "login_and_password"),
                callback_data=f'get_log_pas:{sold_account_id}'
            ),
        )

    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=(
                f"data_by_id:{current_page}" # в просмотр данных по ID
                if for_admin else
                f'sold_account:{sold_account_id}:{type_account_service.value}:{current_page}'
            )
        ),
    )
    return keyboard.as_markup()


def confirm_del_acc_kb(language: str, sold_account_id: int, type_account_service: AccountServiceType, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data=f'del_account:{sold_account_id}:{type_account_service.value}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'sold_account:{sold_account_id}:{type_account_service.value}:{current_page}')
        ]
    ])