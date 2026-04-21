from math import ceil
from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.models.read_models import SoldUniversalSmall
from src.application.keyboards.keyboard_with_pages import pagination_keyboard
from src.application.models.modules import ProfileModule
from src.infrastructure.translations import get_text, n_get_text


def in_purchased_universal_product_kb(
    language: str,
    quantity_products: int,
    sold_universal_id: Optional[int | None] = None
):
    """
    Используется при покупке товара
    :param sold_universal_id: необходим только если приобретается один товар
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=n_get_text(language, "kb_catalog", "to_product", "to_product", quantity_products),
            callback_data=(
                f"sold_universal:{sold_universal_id}:1"
                if sold_universal_id == 1 and sold_universal_id else
                f"all_sold_universal:1"
            )
        )]
    ])


async def sold_universal_kb(
    language: str,
    current_page: int,
    user_id: int,
    profile_module: ProfileModule
):
    records = await profile_module.universal_moduls.sold_service.get_sold_universal_by_page(
        user_id, current_page, language, profile_module.conf.different.page_size
    )
    total = await profile_module.universal_moduls.sold_service.get_count_sold_universal(user_id)
    total_pages = max(ceil(total / profile_module.conf.different.page_size), 1)

    def item_button(sold_universal: SoldUniversalSmall):
        return InlineKeyboardButton(
            text=sold_universal.name if sold_universal.name else str(sold_universal.sold_universal_id),
            callback_data=f"sold_universal:{sold_universal.sold_universal_id}:{current_page}"
        )

    return pagination_keyboard(
        records=records,
        current_page=current_page,
        total_pages=total_pages,
        item_button_func=item_button,
        left_prefix=f"all_sold_universal",
        right_prefix=f"all_sold_universal",
        back_text=get_text(language, "kb_general", "back"),
        back_callback="purchases",
    )


def universal_kb(
    language: str,
    sold_universal_id: int,
    current_page: int,
):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_profile", 'details_product'),
            callback_data=f'get_universal_media:{sold_universal_id}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "delete"),
            callback_data=f'confirm_del_universal:{sold_universal_id}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"all_sold_universal:{current_page}")
        ]
    ])


def confirm_del_universal_kb(language: str, sold_universal_id: int, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data=f'del_universal:{sold_universal_id}:{current_page}',
            style="success",
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'sold_universal:{sold_universal_id}:{current_page}',
            style="danger",
        )]
    ])