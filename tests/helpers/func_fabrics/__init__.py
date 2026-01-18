from tests.helpers.func_fabrics.account_fabric import (
    create_account_storage_factory,
    create_product_account_factory,
    create_sold_account_factory,
    create_tg_account_media_factory,
    make_fake_encrypted_archive_for_test,
    create_purchase_fabric,
)

from tests.helpers.func_fabrics.category_fabric import (
    create_category_factory,
    create_translate_category_factory,
)

from tests.helpers.func_fabrics.other_fabric import (
    create_new_user_fabric,
    create_admin_fabric,
    create_referral_fabric,
    create_income_from_referral_fabric,
    create_replenishment_fabric,
    create_type_payment_factory,
    create_voucher_factory,
    create_ui_image_factory,
    create_transfer_moneys_fabric,
    create_wallet_transaction_fabric,
    create_promo_codes_fabric,
    create_promo_code_activation_fabric,
    create_sent_mass_message_fabric,
    create_backup_log_fabric,
)

from .universal_fabric import (
    create_universal_storage_factory,
    create_product_universal_factory,
    create_sold_universal_factory,
)

__all__ = [
    # Из account_fabric.py
    'create_account_storage_factory',
    'create_product_account_factory',
    'create_sold_account_factory',
    'create_tg_account_media_factory',
    'make_fake_encrypted_archive_for_test',

    # Из category_fabric.py
    'create_category_factory',
    'create_translate_category_factory',

    # Из other_fabric.py
    'create_new_user_fabric',
    'create_admin_fabric',
    'create_referral_fabric',
    'create_income_from_referral_fabric',
    'create_replenishment_fabric',
    'create_type_payment_factory',
    'create_voucher_factory',
    'create_purchase_fabric',
    'create_ui_image_factory',
    'create_transfer_moneys_fabric',
    'create_wallet_transaction_fabric',
    'create_promo_codes_fabric',
    'create_promo_code_activation_fabric',
    'create_sent_mass_message_fabric',
    'create_backup_log_fabric',

    # Из universal_fabric.py
    'create_universal_storage_factory',
    'create_product_universal_factory',
    'create_sold_universal_factory',
]