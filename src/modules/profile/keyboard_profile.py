from math import ceil

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.config import get_config
from src.services.keyboards.keyboard_with_pages import pagination_keyboard
from src.services.database.discounts.actions import get_valid_voucher_by_page
from src.services.database.discounts.actions import get_count_voucher
from src.services.database.referrals.actions import get_referral_income_page, get_count_referral_income
from src.services.database.categories.actions import get_sold_account_by_page
from src.services.database.categories.actions.actions_get import get_count_sold_account, \
    get_union_type_account_service_id, get_all_account_services, get_all_types_account_service, get_type_account_service
from src.services.database.system.actions.actions import get_all_types_payments
from src.services.database.users.actions.action_other_with_user import get_wallet_transaction_page, \
    get_count_wallet_transaction
from src.services.database.users.models import NotificationSettings
from src.utils.i18n import get_text
from src.utils.pars_number import e164_to_pretty


def profile_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Top up your balance'), callback_data='show_type_replenishment')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Purchased accounts'), callback_data='services_sold_accounts')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Balance transfer'), callback_data='balance_transfer')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Referral system'), callback_data='referral_system')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'History transfer'), callback_data=f'transaction_list:{user_id}:1')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Settings'), callback_data='profile_settings')]
    ])

def back_in_profile_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='profile')]
    ])

def in_profile_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'In profile'), callback_data='profile')]
    ])


# ---- Пополнение ----

async def type_replenishment_kb(language: str):
    type_payments = await get_all_types_payments()
    keyboard = InlineKeyboardBuilder()

    for type_payment in type_payments:
        if type_payment.is_active:
            keyboard.row(InlineKeyboardButton(
                text=type_payment.name_for_user,
                callback_data=f'replenishment:{type_payment.type_payment_id}:{type_payment.name_for_user}')
            )

    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='profile'))
    keyboard.adjust(1)
    return keyboard.as_markup()

def payment_invoice(language: str, url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_general', 'Pay'), url=url)],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='show_type_replenishment')]
    ])

def back_in_type_replenishment_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='show_type_replenishment')]
        ])

# ---- Аккаунты ----

async def services_sold_accounts_kb(language: str, user_id: int):
    """Отобразит только те сервисы в которых у пользователя есть купленные аккаунты"""
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
            text=get_text(language, 'kb_profile', 'Others'),
            callback_data=f'all_sold_accounts:1:{type_service_other_id}')
        )

    keyboard.row(
        InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'profile'),
    )

    return keyboard.as_markup()


async def sold_accounts_kb(language: str, current_page: int, type_account_service_id: int, user_id: int):
    records = await get_sold_account_by_page(user_id, type_account_service_id, current_page, language, get_config().different.page_size)
    total = await get_count_sold_account(user_id, type_account_service_id)
    total_pages = max(ceil(total / get_config().different.page_size), 1)

    def item_button(acc):
        text = e164_to_pretty(acc.phone_number) if acc.phone_number else acc.name
        return InlineKeyboardButton(
            text=text,
            callback_data=f"sold_account:{acc.sold_account_id}:{type_account_service_id}:{current_page}"
        )

    return pagination_keyboard(
        records=records,
        current_page=current_page,
        total_pages=total_pages,
        item_button_func=item_button,
        left_prefix=f"all_sold_accounts:{type_account_service_id}",
        right_prefix=f"all_sold_accounts:{type_account_service_id}",
        back_text=get_text(language, "kb_general", "Back"),
        back_callback="services_sold_accounts",
    )


def account_kb(language: str, sold_account_id: int, type_account_service_id: int, current_page: int, current_validity: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'kb_profile', 'Login details'),
            callback_data=f'login_details:{sold_account_id}:{type_account_service_id}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, 'kb_profile', 'Check for validity'),
            # current_validity преобразовал в int что бы занимал меньше места
            callback_data=f'chek_valid_acc:{sold_account_id}:{type_account_service_id}:{current_page}:{int(current_validity)}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Delete"),
            callback_data=f'confirm_del_acc:{sold_account_id}:{type_account_service_id}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'all_sold_accounts:{current_page}:{type_account_service_id}')
        ]
    ])


async def login_details_kb(language: str, sold_account_id: int, type_account_service_id: int, current_page: int):
    type_service = await get_type_account_service(type_account_service_id)
    keyboard = InlineKeyboardBuilder()
    if type_service.name == "telegram":
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, 'kb_profile', 'Get code'),
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
                text=get_text(language, 'kb_profile', 'Login and Password'),
                callback_data=f'get_log_pas:{sold_account_id}'
            ),
        )

    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'sold_account:{sold_account_id}:{type_account_service_id}:{current_page}'
        ),
    )
    return keyboard.as_markup()


def confirm_del_acc_kb(language: str, sold_account_id: int, type_account_service_id: int, current_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Confirm"),
            callback_data=f'del_account:{sold_account_id}:{type_account_service_id}:{current_page}')
        ],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'sold_account:{sold_account_id}:{type_account_service_id}:{current_page}')
        ]
    ])




# ---- Настройки ----

def profile_settings_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Language'), callback_data='selecting_language')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Notification'), callback_data='notification_settings')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='profile')]
    ])

def settings_language_kb(language: str):
    keyboard = InlineKeyboardBuilder()

    for lang in get_config().app.allowed_langs:
        is_current = (lang == language)
        text = f"{'✔️ ' if is_current else ''}{get_config().app.name_langs[lang]}  {get_config().app.emoji_langs[lang]}"
        keyboard.add(InlineKeyboardButton(text=text, callback_data=f'language_selection:{lang}'))

    keyboard.adjust(2)

    # добавляем кнопку "Назад" отдельной строкой
    keyboard.row(InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='profile_settings'))
    return keyboard.as_markup()

def setting_notification_kb(language: str, notification: NotificationSettings):
    return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                text=f'{"✔️ " if notification.referral_invitation else ''}{get_text(language, 'kb_profile', "New referral")}',
                callback_data=f'update_notif:invitation:{"False" if notification.referral_invitation else 'True'}')
            ],
            [
                InlineKeyboardButton(
                    text=f'{"✔️ " if notification.referral_replenishment else ''}{get_text(language, 'kb_profile', "Replenishment referral")}',
                    callback_data=f'update_notif:replenishment:{"False" if notification.referral_replenishment else 'True'}')
            ],
            [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='profile_settings')]
        ])


# ---- Транзакции ----

async def wallet_transactions_kb(language: str, current_page: int, target_user_id: int, user_id: int):
    """
    :param target_user_id: Пользователь по которому будем искать.
    :param user_id: Пользователь, которому выведутся данные
    """
    records = await get_wallet_transaction_page(target_user_id, current_page, get_config().different.page_size)
    total = await get_count_wallet_transaction(target_user_id)
    total_pages = max(ceil(total / get_config().different.page_size), 1)

    def item_button(t):
        return InlineKeyboardButton(
            text=f"{t.amount} ₽   {get_text(language, 'type_wallet_transaction', t.type)}",
            callback_data=f"transaction_show:{target_user_id}:{t.wallet_transaction_id}:{current_page}"
        )

    return pagination_keyboard(
        records=records,
        current_page=current_page,
        total_pages=total_pages,
        item_button_func=item_button,
        left_prefix=f"transaction_list:{target_user_id}",
        right_prefix=f"transaction_list:{target_user_id}",
        back_text=get_text(language, "kb_general", "Back"),
        back_callback=f"profile" if target_user_id == user_id else f"user_management:{target_user_id}"
    )


def back_in_wallet_transactions_kb(language: str, target_user_id: int, currant_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f"transaction_list:{target_user_id}:{currant_page}"
        )
    ]])



# ---- Реферальная система ----

async def ref_system_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, 'kb_profile', 'Information'),
            callback_data=f'ref_system_info',
        )],
        [InlineKeyboardButton(
                text=get_text(language, 'kb_profile', 'Accrual history'),
                callback_data=f'accrual_ref_list:{user_id}:1'
            )
        ],
        [InlineKeyboardButton(
                text=get_text(language, 'kb_profile', 'Download a list of referrals'),
                callback_data=f'download_ref_list:{user_id}'
            )
        ],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'profile')],
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
        back_text=get_text(language, "kb_general", "Back"),
        back_callback=f"referral_system" if target_user_id == user_id else f"user_management:{target_user_id}",
    )

def back_in_accrual_ref_list_kb(language: str, current_page_id: int, target_user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'accrual_ref_list:{target_user_id}:{current_page_id}'
        )]
    ])


def back_in_ref_system_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'referral_system'
        )]
    ])

# ---- Передача баланса ----

def balance_transfer_kb(language: str, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Transfer by id'), callback_data='transfer_money')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Create voucher'), callback_data='create_voucher')],
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'My vouchers'), callback_data=f'voucher_list:{user_id}:1')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'profile')],
    ])

def confirmation_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Confirm"), callback_data='confirm_transfer_money'),
         InlineKeyboardButton(text=get_text(language, "kb_general", "Again"), callback_data='transfer_money')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'balance_transfer')],
    ])

def confirmation_voucher_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Confirm"), callback_data='confirm_create_voucher'),
         InlineKeyboardButton(text=get_text(language, "kb_general", "Again"), callback_data='create_voucher')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'balance_transfer')],
    ])

def back_in_balance_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data=f'balance_transfer')],
    ])


def replenishment_and_back_in_transfer_kb(language: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(language, 'kb_profile', 'Top up your balance'), callback_data='show_type_replenishment')],
        [InlineKeyboardButton(text=get_text(language, "kb_general", "Back"), callback_data='balance_transfer')]
    ])


async def all_vouchers_kb(current_page: int, target_user_id: int, user_id: int, language: str):
    """Клавиатура со списком только активных ваучеров у данного пользователя"""
    records = await get_valid_voucher_by_page(target_user_id, current_page, get_config().different.page_size)
    total = await get_count_voucher(target_user_id)
    total_pages = max(ceil(total / get_config().different.page_size), 1)

    def item_button(voucher):
        return InlineKeyboardButton(
            text=f"{voucher.amount} ₽   {voucher.activation_code}",
            callback_data=f"show_voucher:{target_user_id}:{current_page}:{voucher.voucher_id}"
        )

    return pagination_keyboard(
        records,
        current_page,
        total_pages,
        item_button,
        left_prefix=f"voucher_list:{target_user_id}",
        right_prefix=f"voucher_list:{target_user_id}",
        back_text=get_text(language, "kb_general", "Back"),
        back_callback="transfer_money" if target_user_id == user_id else f"user_management:{target_user_id}",
    )

def show_voucher_kb(language: str, current_page: int, target_user_id: int, user_id: int, voucher_id: int):
    keyboard = InlineKeyboardBuilder()
    if target_user_id == user_id:
        keyboard.row(
            InlineKeyboardButton(
                text=get_text(language, 'kb_profile', 'Deactivate'),
                callback_data=f'confirm_deactivate_voucher:{voucher_id}:{current_page}'
            ),
        )

    keyboard.row(
        InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        ),
    )
    return keyboard.as_markup()

def confirm_deactivate_voucher_kb(language: str, current_page: int, target_user_id: int, voucher_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
                text=get_text(language, "kb_general", "Confirm"),
                callback_data=f'deactivate_voucher:{voucher_id}:{current_page}'
        )],
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        )]
    ])

def back_in_all_voucher_kb(language: str, current_page: int, target_user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=get_text(language, "kb_general", "Back"),
            callback_data=f'voucher_list:{target_user_id}:{current_page}'
        )]
    ])