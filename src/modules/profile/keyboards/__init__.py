from src.modules.profile.keyboards.main_kb import (
    profile_kb,
    back_in_profile_kb,
    in_profile_kb
)

from src.modules.profile.keyboards.purchased_products_kb import (
    type_product_in_purchases_kb,
    sold_account_type_service_kb,
    sold_accounts_kb,
    account_kb,
    login_details_kb,
    confirm_del_acc_kb
)

from src.modules.profile.keyboards.ref_system_kb import (
    ref_system_kb,
    accrual_ref_list_kb,
    back_in_accrual_ref_list_kb,
    back_in_ref_system_kb
)

from src.modules.profile.keyboards.replenishments_kb import (
    type_replenishment_kb,
    payment_invoice,
    back_in_type_replenishment_kb
)

from src.modules.profile.keyboards.settings_kb import (
    profile_settings_kb,
    settings_language_kb,
    setting_notification_kb
)

from src.modules.profile.keyboards.transactions_kb import (
    wallet_transactions_kb,
    back_in_wallet_transactions_kb
)

from src.modules.profile.keyboards.transfer_balance_kb import (
    balance_transfer_kb,
    confirmation_transfer_kb,
    confirmation_voucher_kb,
    back_in_balance_transfer_kb,
    replenishment_and_back_in_transfer_kb,
    all_vouchers_kb,
    show_voucher_kb,
    confirm_deactivate_voucher_kb,
    back_in_all_voucher_kb
)

__all__ = [
    # main_kb.py
    "profile_kb",
    "back_in_profile_kb",
    "in_profile_kb",

    # purchased_products_kb.py
    "type_product_in_purchases_kb",
    "sold_account_type_service_kb",
    "sold_accounts_kb",
    "account_kb",
    "login_details_kb",
    "confirm_del_acc_kb",

    # ref_system_kb.py
    "ref_system_kb",
    "accrual_ref_list_kb",
    "back_in_accrual_ref_list_kb",
    "back_in_ref_system_kb",

    # replenishments_kb.py
    "type_replenishment_kb",
    "payment_invoice",
    "back_in_type_replenishment_kb",

    # settings_kb.py
    "profile_settings_kb",
    "settings_language_kb",
    "setting_notification_kb",

    # transactions_kb.py
    "wallet_transactions_kb",
    "back_in_wallet_transactions_kb",

    # transfer_balance_kb.py
    "balance_transfer_kb",
    "confirmation_transfer_kb",
    "confirmation_voucher_kb",
    "back_in_balance_transfer_kb",
    "replenishment_and_back_in_transfer_kb",
    "all_vouchers_kb",
    "show_voucher_kb",
    "confirm_deactivate_voucher_kb",
    "back_in_all_voucher_kb",
]