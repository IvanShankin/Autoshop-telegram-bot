from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.utils.i18n import get_text


def user_management_kb(language: str, user_id: int, is_ban: bool):
    """
    :param language: язык
    :param user_id: ID пользователя над которым будут совершаться действия
    :param is_ban: флаг бана аккаунта
    """
    if is_ban:
        ban_text = get_text(language, 'keyboard', 'Remove the ban')
    else:
        ban_text = get_text(language, 'keyboard', 'Issue a ban')

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard','Change Balance'),
            callback_data=f"change_user_bal:{user_id}"
        )],
        [InlineKeyboardButton(
            text=ban_text,
            callback_data=f"confirm_remove_ban:{user_id}" if is_ban else f'issue_ban:{user_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Unload All Actions'),
            callback_data=f"unload_action_user:{user_id}"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Transaction History'),
            callback_data=f"transaction_list:{user_id}:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Unload Referral List'),
            callback_data=f'download_ref_list:{user_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Referral Credit History'),
            callback_data=f"accrual_ref_list:{user_id}:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Active vouchers'),
            callback_data=f"voucher_list:{user_id}:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"admin_panel"
        )],
    ])


def back_in_user_management_kb(language: str, user_id: int):
    """
    :param user_id: ID пользователя над которым будут совершаться действия
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"user_management:{user_id}"
        )],
    ])


def confirm_remove_ban_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Confirm'),
            callback_data=f"remove_ban:{user_id}"
        )],
        [InlineKeyboardButton(
            text=get_text(language, 'keyboard', 'Back'),
            callback_data=f"user_management:{user_id}"
        )],
    ])

