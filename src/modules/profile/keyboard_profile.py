from math import ceil
from typing import List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot_actions.bot_instance import get_bot
from src.config import ALLOWED_LANGS, NAME_LANGS, EMOJI_LANGS, PAGE_SIZE
from src.services.referrals.actions.actions_ref import get_referral_income_page, get_count_referral_income
from src.services.system.actions import get_settings
from src.services.users.models import NotificationSettings, WalletTransaction
from src.utils.i18n import get_i18n


def profile_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Top up your balance'), callback_data='money_replenishment')],
        [InlineKeyboardButton(text=i18n.gettext('Purchased accounts'), callback_data='purchased_accounts')],
        [InlineKeyboardButton(text=i18n.gettext('Balance transfer'), callback_data='balance_transfer')],
        [InlineKeyboardButton(text=i18n.gettext('Referral system'), callback_data='referral_system')],
        [InlineKeyboardButton(text=i18n.gettext('History transfer'), callback_data='history_transaction')],
        [InlineKeyboardButton(text=i18n.gettext('Settings'), callback_data='profile_settings')]
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

def all_wallet_transactions_kb(transactions: List[WalletTransaction], language: str):
    i18n = get_i18n(language, "type_wallet_transaction")
    keyboard = InlineKeyboardBuilder()
    transactions = transactions[:100] # Обрезаем список. Максимальное количество кнопок - 100

    for transaction in transactions:
        keyboard.add(InlineKeyboardButton(
            text=f"{transaction.amount} ₽   {i18n.gettext(transaction.type)}",
            callback_data=f'show_transaction:{transaction.wallet_transaction_id}')
        )

    i18n = get_i18n(language, "keyboard_dom")
    keyboard.add(InlineKeyboardButton(
        text=i18n.gettext('Back'),
        callback_data=f'profile')
    )

    keyboard.adjust(1)
    return keyboard.as_markup()

def back_in_wallet_transactions_kb(language: str):
    i18n = get_i18n(language, "keyboard_dom")
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='history_transaction')]
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


async def all_accrual_history_kb(language: str, current_page: int, user_id: int):
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
            InlineKeyboardButton(text=" ", callback_data=f"none"),
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


