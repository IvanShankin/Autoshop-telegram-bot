from src.config import get_config


def get_ui_images():
    ui_sections = get_config().paths.ui_sections_dir
    return {
        # Начальные экраны
        "welcome_message": ui_sections / "welcome_message.png",
        "selecting_language": ui_sections / "selecting_language.png",
        "subscription_prompt": ui_sections / "subscription_prompt.png",

        # Основные разделы профиля
        "profile": ui_sections / "profile.png",
        "profile_settings": ui_sections / "profile_settings.png",
        "notification_settings": ui_sections / "notification_settings.png",

        # покупки
        "purchases": ui_sections / "purchases.png",
        "purchased_accounts": ui_sections / "purchased_accounts.png",
        "purchased_universal": ui_sections / "purchased_universal.png",

        # История операций
        "history_transections": ui_sections / "history_transections.png",
        "history_income_from_referrals": ui_sections / "history_income_from_referrals.png",

        # Реферальная система
        "ref_system": ui_sections / "ref_system.png",
        "new_referral": ui_sections / "new_referral.png",

        # Перевод средств
        "balance_transfer": ui_sections / "balance_transfer.png",
        "enter_amount": ui_sections / "enter_amount.png",
        "enter_user_id": ui_sections / "enter_user_id.png",
        "confirm_the_data": ui_sections / "confirm_the_data.png",
        "successful_transfer": ui_sections / "successful_transfer.png",
        "receiving_funds_from_transfer": ui_sections / "receiving_funds_from_transfer.png",

        # Ваучеры
        "enter_number_activations_for_voucher": ui_sections / "enter_number_activations_for_voucher.png",
        "successful_create_voucher": ui_sections / "successful_create_voucher.png",
        "successfully_activate_voucher": ui_sections / "successfully_activate_voucher.png",
        "unsuccessfully_activate_voucher": ui_sections / "unsuccessfully_activate_voucher.png",
        "viewing_vouchers": ui_sections / "viewing_vouchers.png",
        "confirm_deactivate_voucher": ui_sections / "confirm_deactivate_voucher.png",
        "voucher_successful_deactivate": ui_sections / "voucher_successful_deactivate.png",

        # Ошибки
        "insufficient_funds": ui_sections / "insufficient_funds.png", # недостаточно средств
        "incorrect_data_entered": ui_sections / "incorrect_data_entered.png",
        "user_no_found": ui_sections / "user_no_found.png",
        "server_error": ui_sections / "server_error.png",

        # Пополнение
        "show_all_services_replenishments": ui_sections / "show_all_services_replenishments.png",
        "request_enter_amount": ui_sections / "request_enter_amount.png",
        "pay": ui_sections / "pay.png", # успешная оплата при пополнении

        # каталог
        "main_catalog": ui_sections / "main_catalog.png",
        "default_catalog_account": ui_sections / "default_catalog_account.png",
        "main_category": ui_sections / "main_category.png",
        "confirm_purchase": ui_sections / "confirm_purchase.png",
        "successful_purchase": ui_sections / "successful_purchase.png",

        # промокод
        "entering_promo_code": ui_sections / "entering_promo_code.png",

        # админ панель
        "admin_panel": ui_sections / "admin_panel.png",
        "info_add_accounts": ui_sections / "info_add_accounts.png",
        "example_csv": ui_sections / "example_csv.png",

        # тех работы
        "technical_work": ui_sections / "technical_work.png",

    }

UI_IMAGES_IGNORE_ADMIN = ["info_add_accounts", "example_csv"]