from math import ceil

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.application.keyboards.keyboard_with_pages import pagination_keyboard
from src.application.models.modules import ProfileModule
from src.utils.i18n import get_text


async def wallet_transactions_kb(
    language: str,
    current_page: int,
    target_user_id: int,
    user_id: int,
    profile_module: ProfileModule
):
    """
    :param target_user_id: Пользователь по которому будем искать.
    :param user_id: Пользователь, которому выведутся данные
    """
    records = await profile_module.wallet_transaction_service.get_wallet_transaction_page(
        target_user_id, current_page, profile_module.conf.different.page_size
    )
    total = await profile_module.wallet_transaction_service.get_count_wallet_transaction(target_user_id)
    total_pages = max(ceil(total / profile_module.conf.different.page_size), 1)

    def item_button(t):
        return InlineKeyboardButton(
            text=f"{t.amount} ₽   {get_text(language, "type_wallet_transaction", t.type)}",
            callback_data=f"transaction_show:{target_user_id}:{t.wallet_transaction_id}:{current_page}"
        )

    return pagination_keyboard(
        records=records,
        current_page=current_page,
        total_pages=total_pages,
        item_button_func=item_button,
        left_prefix=f"transaction_list:{target_user_id}",
        right_prefix=f"transaction_list:{target_user_id}",
        back_text=get_text(language, "kb_general", "back"),
        back_callback=f"profile" if target_user_id == user_id else f"user_management:{target_user_id}"
    )


def back_in_wallet_transactions_kb(language: str, target_user_id: int, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"transaction_list:{target_user_id}:{current_page}"
        )
    ]])

