from math import ceil

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.config import get_config
from src.services.database.referrals.actions import get_referral_income_page, get_count_referral_income
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.utils.i18n import get_text


async def ref_system_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_profile", 'information'),
            callback_data=f'ref_system_info',
        )],
        [InlineKeyboardButton(
                text=get_text(language, "kb_profile", "accrual_history"),
                callback_data=f'accrual_ref_list:{user_id}:1'
            )
        ],
        [InlineKeyboardButton(
                text=get_text(language, "kb_profile", "download_list_referrals"),
                callback_data=f'download_ref_list:{user_id}'
            )
        ],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "back"), callback_data=f'profile')],
    ])


async def accrual_ref_list_kb(language: str, current_page: int, target_user_id: int, user_id: int):
    """
    :param target_user_id: Пользователь по которому будем искать.
    :param user_id: Пользователь, которому выведутся данные
    """
    records = await get_referral_income_page(target_user_id, current_page, get_config().different.page_size)
    total = await get_count_referral_income(target_user_id)
    total_pages = max(ceil(total / get_config().different.page_size), 1)

    def item_button(inc):
        return InlineKeyboardButton(
            text=f"{inc.amount} ₽",
            callback_data=f"detail_income_from_ref:{inc.income_from_referral_id}:{current_page}"
        )

    return pagination_keyboard(
        records,
        current_page,
        total_pages,
        item_button,
        left_prefix=f"accrual_ref_list:{target_user_id}",
        right_prefix=f"accrual_ref_list:{target_user_id}",
        back_text=get_text(language, "kb_general", "back"),
        back_callback=f"referral_system" if target_user_id == user_id else f"user_management:{target_user_id}",
    )

def back_in_accrual_ref_list_kb(language: str, current_page_id: int, target_user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'accrual_ref_list:{target_user_id}:{current_page_id}'
        )]
    ])


def back_in_ref_system_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f'referral_system'
        )]
    ])
