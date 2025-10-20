from math import ceil

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot_actions.bot_instance import get_bot
from src.config import ALLOWED_LANGS, NAME_LANGS, EMOJI_LANGS, PAGE_SIZE
from src.services.discounts.actions import get_valid_voucher_by_user_page
from src.services.discounts.actions.actions_vouchers import get_count_voucher
from src.services.referrals.actions.actions_ref import get_referral_income_page, get_count_referral_income
from src.services.system.actions import get_settings
from src.services.users.actions.action_other_with_user import get_wallet_transaction_page, get_count_wallet_transaction
from src.services.users.models import NotificationSettings
from src.utils.i18n import get_i18n


def profile_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Top up your balance'), callback_data='money_replenishment')],
        [InlineKeyboardButton(text=i18n.gettext('Purchased accounts'), callback_data='purchased_accounts')],
        [InlineKeyboardButton(text=i18n.gettext('Balance transfer'), callback_data='balance_transfer')],
        [InlineKeyboardButton(text=i18n.gettext('Referral system'), callback_data='referral_system')],
        [InlineKeyboardButton(text=i18n.gettext('History transfer'), callback_data='history_transaction:1')],
        [InlineKeyboardButton(text=i18n.gettext('Settings'), callback_data='profile_settings')]
    ])

def back_in_profile_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile')]
    ])

# ---- Настройки ----

def profile_settings_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Language'), callback_data='selecting_language')],
        [InlineKeyboardButton(text=i18n.gettext('Notification'), callback_data='notification_settings')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile')]
    ])

def settings_language_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    keyboard = InlineKeyboardBuilder()

    for lang in ALLOWED_LANGS:
        is_current = (lang == language)
        text = f"{'✔️ ' if is_current else ''}{NAME_LANGS[lang]}  {EMOJI_LANGS[lang]}"
        keyboard.add(InlineKeyboardButton(text=text, callback_data=f'language_selection:{lang}'))

    keyboard.adjust(2)

    # добавляем кнопку "Назад" отдельной строкой
    keyboard.row(InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile_settings'))
    return keyboard.as_markup()

def setting_notification_kb(language: str, notification: NotificationSettings):
    i18n = get_i18n(language, 'keyboard_dom')

    return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                text=f'{"✔️ " if notification.referral_invitation else ''}{i18n.gettext("New referral")}',
                callback_data=f'update_notif:invitation:{"False" if notification.referral_invitation else 'True'}')
            ],
            [
                InlineKeyboardButton(
                    text=f'{"✔️ " if notification.referral_replenishment else ''}{i18n.gettext("Replenishment referral")}',
                    callback_data=f'update_notif:replenishment:{"False" if notification.referral_replenishment else 'True'}')
            ],
            [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile_settings')]
        ])


# ---- Транзакции ----

async def wallet_transactions_kb(language: str, current_page: int, user_id: int):
    records = await get_wallet_transaction_page(user_id, current_page, PAGE_SIZE)
    total = await get_count_wallet_transaction(user_id)
    total_pages = max(ceil(total / PAGE_SIZE), 1)
    i18n = get_i18n(language, "type_wallet_transaction")

    keyboard = InlineKeyboardBuilder()

    for transaction in records:
        keyboard.row(InlineKeyboardButton(
            text=f"{transaction.amount} ₽   {i18n.gettext(transaction.type)}",
            callback_data=f'show_transaction:{transaction.wallet_transaction_id}')
        )

    if records and total_pages > 1:
        left_button = f"history_transaction_none"
        right_button = f"history_transaction_none"
        if current_page > 1 and total_pages > current_page:  # если есть куда двинуться направо и налево
            left_button = f"history_transaction:{current_page - 1}"
            right_button = f"history_transaction:{current_page + 1}"
        elif current_page == 1:  # если есть записи только впереди
            right_button = f"history_transaction:{current_page + 1}"
        elif current_page > 1:  # если есть записи только позади
            left_button = f"history_transaction:{current_page - 1}"

        keyboard.row(
            InlineKeyboardButton(text="⬅️", callback_data=left_button),
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data=f"none"),
            InlineKeyboardButton(text="➡️", callback_data=right_button)
        )

    i18n = get_i18n(language, "keyboard_dom")
    keyboard.row(
        InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'profile'),
    )

    return keyboard.as_markup()

def back_in_wallet_transactions_kb(language: str):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='history_transaction:1')]
        ])


# ---- Реферальная система ----

async def ref_system_kb(language: str):
    i18n = get_i18n(language, "keyboard_dom")
    settings = await get_settings()

    if not settings.linc_info_ref_system:
        bot = await get_bot()
        bot_me = await bot.me()
        url = f'https://web.telegram.org/k/#@{bot_me.username}'
    else:
        url = settings.linc_info_ref_system

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Information'), url=url)],
        [InlineKeyboardButton(text=i18n.gettext('Accrual history'), callback_data='accrual_history:1')],
        [InlineKeyboardButton(text=i18n.gettext('Download a list of referrals'), callback_data='download_ref_list')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'profile')],
    ])


async def accruals_history_kb(language: str, current_page: int, user_id: int):
    records = await get_referral_income_page(user_id, current_page, PAGE_SIZE)
    total = await get_count_referral_income(user_id)
    total_pages = max(ceil(total / PAGE_SIZE), 1)
    i18n = get_i18n(language, "keyboard_dom")

    keyboard = InlineKeyboardBuilder()

    for income in records:
        keyboard.row(InlineKeyboardButton(
            text=f"{income.amount} ₽",
            callback_data=f'detail_income_from_ref:{income.income_from_referral_id}:{current_page}')
        )

    if records and total_pages > 1:
        left_button = f"accrual_history_none"
        right_button = f"accrual_history_none"
        if current_page > 1 and total_pages > current_page: # если есть куда двинуться направо и налево
            left_button = f"accrual_history:{current_page - 1}"
            right_button = f"accrual_history:{current_page + 1}"
        elif current_page == 1: # если есть записи только впереди
            right_button = f"accrual_history:{current_page + 1}"
        elif current_page > 1: # если есть записи только позади
            left_button = f"accrual_history:{current_page - 1}"

        keyboard.row(
            InlineKeyboardButton(text="⬅️", callback_data=left_button),
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data=f"none"),
            InlineKeyboardButton(text="➡️", callback_data=right_button)
        )

    keyboard.row(
        InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'referral_system'),
    )

    return keyboard.as_markup()

async def back_in_accrual_history_kb(language: str, current_page_id: int):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'accrual_history:{current_page_id}')]
    ])


# ---- Передача баланса ----

def balance_transfer_kb(language: str):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Transfer by id'), callback_data='transfer_money')],
        [InlineKeyboardButton(text=i18n.gettext('Create voucher'), callback_data='create_voucher')],
        [InlineKeyboardButton(text=i18n.gettext('My vouchers'), callback_data=f'my_voucher:1')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'profile')],
    ])

def confirmation_transfer_kb(language: str):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Confirm'), callback_data='confirm_transfer_money'),
         InlineKeyboardButton(text=i18n.gettext('Again'), callback_data='transfer_money')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'balance_transfer')],
    ])

def confirmation_voucher_kb(language: str):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Confirm'), callback_data='confirm_create_voucher'),
         InlineKeyboardButton(text=i18n.gettext('Again'), callback_data='create_voucher')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'balance_transfer')],
    ])

def back_in_balance_transfer_kb(language: str):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'balance_transfer')],
    ])

def replenishment_and_back_in_transfer_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Top up your balance'), callback_data='money_replenishment')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='balance_transfer')]
    ])

async def all_vouchers_kb(user_id: int, current_page: int, language: str):
    """Клавиатура со списком только активных ваучеров у данного пользователя"""
    records = await get_valid_voucher_by_user_page(user_id, current_page, PAGE_SIZE)
    total = await get_count_voucher(user_id)
    total_pages = max(ceil(total / PAGE_SIZE), 1)

    keyboard = InlineKeyboardBuilder()

    for voucher in records:
        keyboard.row(InlineKeyboardButton(
            text=f"{voucher.amount} ₽   {voucher.activation_code}",
            callback_data=f'show_voucher:{voucher.voucher_id}:{current_page}')
        )

    if records and total_pages > 1:
        left_button = f"my_voucher_none"
        right_button = f"my_voucher_none"
        if current_page > 1 and total_pages > current_page:  # если есть куда двинуться направо и налево
            left_button = f"my_voucher:{current_page - 1}"
            right_button = f"my_voucher:{current_page + 1}"
        elif current_page == 1:  # если есть записи только впереди
            right_button = f"my_voucher:{current_page + 1}"
        elif current_page > 1:  # если есть записи только позади
            left_button = f"my_voucher:{current_page - 1}"

        keyboard.row(
            InlineKeyboardButton(text="⬅️", callback_data=left_button),
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data=f"none"),
            InlineKeyboardButton(text="➡️", callback_data=right_button)
        )

    i18n = get_i18n(language, "keyboard_dom")
    keyboard.row(
        InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'profile'),
    )

    return keyboard.as_markup()

def show_voucher_kb(language: str, current_page: int, voucher_id: int):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Deactivate'), callback_data=f'confirm_deactivate_voucher:{voucher_id}:{current_page}')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'my_voucher:{current_page}')]
    ])

def confirm_deactivate_voucher_kb(language: str, current_page: int, voucher_id: int):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Confirm'), callback_data=f'deactivate_voucher:{voucher_id}:{current_page}')],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'my_voucher:{current_page}')]
    ])

def back_in_all_voucher_kb(language: str, current_page: int):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'my_voucher:{current_page}')]
    ])