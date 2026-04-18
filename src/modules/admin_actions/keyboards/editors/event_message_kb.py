from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.application.keyboards.keyboard_with_pages import pagination_keyboard
from src.application.models.modules import AdminModule
from src.infrastructure.translations import get_text


async def images_list_kb(language: str, current_page: int, admin_module: AdminModule,):
    event_message_keys = await admin_module.event_message_service.get_event_message_by_page(current_page)
    conf = admin_module.conf
    total_pages = max(ceil((len(conf.message_event.all_keys) - len(conf.message_event.keys_ignore_admin)) / admin_module.conf.different.page_size), 1)

    def item_button(event_msg_key):
        return InlineKeyboardButton(text=event_msg_key, callback_data=f'choice_edit_event_msg:{event_msg_key}:{current_page}')

    return pagination_keyboard(
        records=event_message_keys,
        current_page=current_page,
        total_pages=total_pages,
        item_button_func=item_button,
        left_prefix=f"event_msg_editor_list",
        right_prefix=f"event_msg_editor_list",
        back_text=get_text(language, "kb_general", "back"),
        back_callback=f"editors"
    )


async def choice_edit_event_msg_kb(language: str, event_msg_key: str, current_page: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", "change_image"),
                callback_data=f'edit_image:{event_msg_key}:{current_page}'
            )],
            [InlineKeyboardButton(
                text=get_text(language, "kb_admin_panel", "change_sticker"),
                callback_data=f'edit_sticker:{event_msg_key}:{current_page}'
            )],
            [InlineKeyboardButton(
                text=get_text(language, "kb_general", "back"),
                callback_data=f'event_msg_editor_list:{current_page}'
            )],
        ],
    )


async def image_editor(language: str, event_msg_key: str, current_show: bool, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "change_image"),
            callback_data=f'change_ui_image:{event_msg_key}:{current_page}'),
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "show_indicator").format(indicator='🟢' if current_show else '🔴'),
            callback_data=f"ui_image_update_show:{event_msg_key}:{0 if current_show else 1}:{current_page}"),
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'choice_edit_event_msg:{event_msg_key}:{current_page}'),
        ]
    ])


async def sticker_editor_kb(language: str, event_msg_key: str, current_show: bool, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "change_sticker"),
            callback_data=f'change_sticker:{event_msg_key}:{current_page}'),
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "show_indicator").format(indicator='🟢' if current_show else '🔴'),
            callback_data=f"sticker_update_show:{event_msg_key}:{0 if current_show else 1}:{current_page}"),
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "show_current"),
            callback_data=f'show_current_sticker:{event_msg_key}'),
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'choice_edit_event_msg:{event_msg_key}:{current_page}'),
        ]
    ])


async def back_in_image_editor(language: str, event_msg_key: str, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'edit_image:{event_msg_key}:{current_page}'), ]
    ])


async def back_in_sticker_editor(language: str, event_msg_key: str, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'edit_sticker:{event_msg_key}:{current_page}'), ]
    ])