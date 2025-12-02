from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import PAGE_SIZE
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.utils.i18n import get_text
from src.utils.ui_images_data import UI_IMAGES, get_ui_images_by_page


async def images_list_kb(language: str, current_page: int):
    images = get_ui_images_by_page(current_page)
    total_pages = max(ceil(len(UI_IMAGES) / PAGE_SIZE), 1)

    def item_button(img_key):
        return InlineKeyboardButton(text=img_key, callback_data=f'edit_image:{img_key}:{current_page}')

    return pagination_keyboard(
        records=images,
        current_page=current_page,
        total_pages=total_pages,
        item_button_func=item_button,
        left_prefix=f"images_editor_list",
        right_prefix=f"images_editor_list",
        back_text=get_text(language, 'keyboard', 'Back'),
        back_callback=f"editors"
    )


async def image_editor(language: str, ui_image_key: str, current_show: bool, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "Change image"),
            callback_data=f'change_ui_image:{ui_image_key}:{current_page}'),
        ],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', "{indicator} Show").format(indicator='🟢' if current_show else '🔴'),
            callback_data=f"ui_image_update_show:{ui_image_key}:{0 if current_show else 1}:{current_page}"),
        ],
        [InlineKeyboardButton(text=get_text(language, 'keyboard', 'Back'), callback_data=f'images_editor_list:{current_page}'), ]
    ])

async def back_in_image_editor(language: str, img_key: str, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f'edit_image:{img_key}:{current_page}'), ]
    ])