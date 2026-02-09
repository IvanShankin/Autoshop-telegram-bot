def get_ui_images():
    return {
        # Начальные экраны
        "welcome_message",
        "selecting_language",
        "subscription_prompt",
        "info",

        # Основные разделы профиля
        "profile",
        "profile_settings",
        "notification_settings",

        # покупки
        "purchases",
        "purchased_accounts",
        "purchased_universal",

        # История операций
        "history_transections",
        "history_income_from_referrals",

        # Реферальная система
        "ref_system",
        "new_referral",

        # Перевод средств
        "balance_transfer",
        "enter_amount",
        "enter_user_id",
        "confirm_the_data",
        "successful_transfer",
        "receiving_funds_from_transfer",

        # Ваучеры
        "enter_number_activations_for_voucher",
        "successful_create_voucher",
        "successfully_activate_voucher",
        "unsuccessfully_activate_voucher",
        "viewing_vouchers",
        "confirm_deactivate_voucher",
        "voucher_successful_deactivate",

        # Ошибки
        "insufficient_funds",
        "incorrect_data_entered",
        "user_no_found",
        "server_error",

        # Пополнение
        "show_all_services_replenishments",
        "request_enter_amount",
        "pay",

        # каталог
        "main_catalog",
        "default_catalog_account",
        "main_category",
        "confirm_purchase",
        "successful_purchase",

        # промокод
        "entering_promo_code",

        # админ панель
        "admin_panel",
        "info_add_accounts",
        "example_csv",

        # тех работы
        "technical_work",
    }

UI_IMAGES_IGNORE_ADMIN = ["info_add_accounts", "example_csv"]