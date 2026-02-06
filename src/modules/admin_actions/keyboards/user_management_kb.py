from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.utils.i18n import get_text


def user_management_kb(language: str, user_id: int, is_ban: bool):
    """
    :param language: язык
    :param user_id: ID пользователя над которым будут совершаться действия
    :param is_ban: флаг бана аккаунта
    """
    if is_ban:
        ban_text = get_text(language, "kb_admin_panel", "remove_ban")
    else:
        ban_text = get_text(language, "kb_admin_panel", "issue_ban")

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel","change_balance"),
            callback_data=f"change_user_bal:{user_id}"
        )],
        [InlineKeyboardButton(
            text=ban_text,
            callback_data=f"confirm_remove_ban:{user_id}" if is_ban else f'issue_ban:{user_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "unload_all_actions"),
            callback_data=f"unload_action_user:{user_id}"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "transaction_history"),
            callback_data=f"transaction_list:{user_id}:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "unload_referral_list"),
            callback_data=f'download_ref_list:{user_id}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "referral_credit_history"),
            callback_data=f"accrual_ref_list:{user_id}:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_admin_panel", "active_vouchers"),
            callback_data=f"voucher_list:{user_id}:1"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"admin_panel"
        )],
    ])


def back_in_user_management_kb(language: str, user_id: int):
    """
    :param user_id: ID пользователя над которым будут совершаться действия
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"user_management:{user_id}"
        )],
    ])


def confirm_remove_ban_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "confirm"),
            callback_data=f"remove_ban:{user_id}"
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "back"),
            callback_data=f"user_management:{user_id}"
        )],
    ])

