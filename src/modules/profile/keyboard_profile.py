from math import ceil

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot_actions.bot_instance import get_bot
from src.config import ALLOWED_LANGS, NAME_LANGS, EMOJI_LANGS, PAGE_SIZE
from src.services.database.discounts.actions import get_valid_voucher_by_user_page
from src.services.database.discounts.actions import get_count_voucher
from src.services.database.referrals.actions.actions_ref import get_referral_income_page, get_count_referral_income
from src.services.database.selling_accounts.actions import get_sold_account_by_page
from src.services.database.selling_accounts.actions.actions_get import get_count_sold_account, \
    get_union_type_account_service_id, get_all_account_services, get_all_types_account_service, get_type_account_service
from src.services.database.system.actions import get_settings
from src.services.database.system.actions.actions import get_all_types_payments
from src.services.database.users.actions.action_other_with_user import get_wallet_transaction_page, \
    get_count_wallet_transaction
from src.services.database.users.models import NotificationSettings
from src.utils.i18n import get_i18n


def profile_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Top up your balance'), callback_data='show_type_replenishment')],
        [InlineKeyboardButton(text=i18n.gettext('Purchased accounts'), callback_data='services_sold_accounts')],
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

def in_profile_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('In profile'), callback_data='profile')]
    ])


# ---- Пополнение ----

async def type_replenishment_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    type_payments = await get_all_types_payments()
    keyboard = InlineKeyboardBuilder()

    for type_payment in type_payments:
        if type_payment.is_active:
            keyboard.row(InlineKeyboardButton(
                text=type_payment.name_for_user,
                callback_data=f'replenishment:{type_payment.type_payment_id}:{type_payment.name_for_user}')
            )

    keyboard.row(InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='profile'))
    keyboard.adjust(1)
    return keyboard.as_markup()

def payment_invoice(language: str, url: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.gettext('Pay'), url=url)],
        [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='show_type_replenishment')]
    ])

def back_in_type_replenishment_kb(language: str):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.gettext('Back'), callback_data='show_type_replenishment')]
        ])

# ---- Аккаунты ----

async def services_sold_accounts_kb(language: str, user_id: int):
    """Отобразит только те сервисы в которых у пользователя есть купленные аккаунты"""
    i18n = get_i18n(language, "keyboard_dom")
    union_type_service_ids = await get_union_type_account_service_id(user_id)
    account_services = await get_all_account_services(return_not_show=True)

    # определяем id типа сервиса 'other'
    all_type_services = await get_all_types_account_service()
    type_service_other_id = next(
        (s.type_account_service_id for s in all_type_services if s.name == 'other'),
        -1
    )

    keyboard = InlineKeyboardBuilder()

    # сперва пытаемся получить имя с созданных сервисов
    used_type_service = []
    for service in account_services:
        if (service.type_account_service_id in union_type_service_ids and
            service.type_account_service_id != type_service_other_id):

            keyboard.row(InlineKeyboardButton(
                text=service.name,
                callback_data=f'all_sold_accounts:1:{service.type_account_service_id}')
            )
            used_type_service.append(service.type_account_service_id)


    # если нет некоторых созданных сервисов, то устанавливаем имя которое находится в типе сервиса
    unused_ids = [service_id for service_id in union_type_service_ids if service_id not in used_type_service]
    for type_service_id in unused_ids:
        if type_service_id != type_service_other_id:

            for type_service in all_type_services:
                if type_service.type_account_service_id == type_service_id:
                    keyboard.row(InlineKeyboardButton(
                        text=type_service.name,
                        callback_data=f'all_sold_accounts:1:{type_service_id}')
                    )
                    break

    # тип сервиса "other" должен быть всегда последним
    if type_service_other_id in union_type_service_ids:
        keyboard.row(InlineKeyboardButton(
            text=i18n.gettext('Others'),
            callback_data=f'all_sold_accounts:1:{type_service_other_id}')
        )

    keyboard.row(
        InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'profile'),
    )

    return keyboard.as_markup()


async def sold_accounts_kb(language: str, current_page: int, type_account_service_id: int, user_id: int):
    records = await get_sold_account_by_page(user_id, type_account_service_id, current_page, language, PAGE_SIZE)
    total = await get_count_sold_account(user_id, type_account_service_id)
    total_pages = max(ceil(total / PAGE_SIZE), 1)

    keyboard = InlineKeyboardBuilder()

    for account in records:
        keyboard.row(InlineKeyboardButton(
            text=account.phone_number if account.phone_number else account.name,
            callback_data=f'sold_account:{account.sold_account_id}:{type_account_service_id}:{current_page}')
        )

    if records and total_pages > 1:
        left_button = f"all_sold_accounts_none"
        right_button = f"all_sold_accounts_none"
        if current_page > 1 and total_pages > current_page:  # если есть куда двинуться направо и налево
            left_button = f"all_sold_accounts:{current_page - 1}:{type_account_service_id}"
            right_button = f"all_sold_accounts:{current_page + 1}:{type_account_service_id}"
        elif current_page == 1:  # если есть записи только впереди
            right_button = f"all_sold_accounts:{current_page + 1}:{type_account_service_id}"
        elif current_page > 1:  # если есть записи только позади
            left_button = f"all_sold_accounts:{current_page - 1}:{type_account_service_id}"

        keyboard.row(
            InlineKeyboardButton(text="⬅️", callback_data=left_button),
            InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data=f"none"),
            InlineKeyboardButton(text="➡️", callback_data=right_button)
        )

    i18n = get_i18n(language, "keyboard_dom")
    keyboard.row(
        InlineKeyboardButton(text=i18n.gettext('Back'), callback_data=f'services_sold_accounts'),
    )

    return keyboard.as_markup()


def account_kb(language: str, sold_account_id: int, type_account_service_id: int, current_page: int, current_validity: bool):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=i18n.gettext('Login details'),
            callback_data=f'login_details:{sold_account_id}:{type_account_service_id}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=i18n.gettext('Check for validity'),
            # current_validity преобразовал в int что бы занимал меньше места
            callback_data=f'chek_valid_acc:{sold_account_id}:{type_account_service_id}:{current_page}:{int(current_validity)}')
        ],
        [InlineKeyboardButton(
            text=i18n.gettext('Delete'),
            callback_data=f'confirm_del_acc:{sold_account_id}:{type_account_service_id}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=i18n.gettext('Back'),
            callback_data=f'all_sold_accounts:{current_page}:{type_account_service_id}')
        ]
    ])


async def login_details_kb(language: str, sold_account_id: int, type_account_service_id: int, current_page: int):
    i18n = get_i18n(language, 'keyboard_dom')

    type_service = await get_type_account_service(type_account_service_id)
    keyboard = InlineKeyboardBuilder()
    if type_service.name == "telegram":
        keyboard.row(
            InlineKeyboardButton(
                text=i18n.gettext('Get code'),
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
                text=i18n.gettext('Login and Password'),
                callback_data=f'get_log_pas:{sold_account_id}'
            ),
        )

    keyboard.row(
        InlineKeyboardButton(
            text=i18n.gettext('Back'),
            callback_data=f'sold_account:{sold_account_id}:{type_account_service_id}:{current_page}'
        ),
    )
    return keyboard.as_markup()


def confirm_del_acc_kb(language: str, sold_account_id: int, type_account_service_id: int, current_page: int):
    i18n = get_i18n(language, 'keyboard_dom')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=i18n.gettext('Confirm'),
            callback_data=f'del_account:{sold_account_id}:{type_account_service_id}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=i18n.gettext('Back'),
            callback_data=f'sold_account:{sold_account_id}:{type_account_service_id}:{current_page}')
        ]
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
        [InlineKeyboardButton(text=i18n.gettext('Top up your balance'), callback_data='show_type_replenishment')],
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