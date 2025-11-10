from src.config import MEDIA_DIR
from io import BytesIO
from PIL import Image

UI_SECTIONS = MEDIA_DIR / "ui_sections"


def get_default_image_bytes(color: str = "white", size: tuple[int, int] = (500, 500)) -> bytes:
    """
    Создаёт изображение-заглушку и возвращает его в виде байтов (PNG).
    Подходит для передачи в create_ui_image как file_data.
    """
    img = Image.new("RGB", size, color=color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


UI_IMAGES = {
    # дефолтный путь к изображению заглушки
    "default_catalog_account": UI_SECTIONS / "default_catalog_account.png",

    # Начальные экраны
    "welcome_message": UI_SECTIONS / "welcome_message.png",
    "selecting_language": UI_SECTIONS / "selecting_language.png",
    "subscription_prompt": UI_SECTIONS / "subscription_prompt.png",

    # Основные разделы профиля
    "profile": UI_SECTIONS / "profile.png",
    "profile_settings": UI_SECTIONS / "profile_settings.png",
    "notification_settings": UI_SECTIONS / "notification_settings.png",

    # История операций
    "history_transections": UI_SECTIONS / "history_transections.png",
    "history_income_from_referrals": UI_SECTIONS / "history_income_from_referrals.png",

    # Реферальная система
    "ref_system": UI_SECTIONS / "ref_system.png",
    "new_referral": UI_SECTIONS / "new_referral.png",

    # Перевод средств
    "balance_transfer": UI_SECTIONS / "balance_transfer.png",
    "enter_amount": UI_SECTIONS / "enter_amount.png",
    "enter_user_id": UI_SECTIONS / "enter_user_id.png",
    "confirm_the_data": UI_SECTIONS / "confirm_the_data.png",
    "successful_transfer": UI_SECTIONS / "successful_transfer.png",
    "receiving_funds_from_transfer": UI_SECTIONS / "receiving_funds_from_transfer.png",

    # Ваучеры
    "enter_number_activations_for_voucher": UI_SECTIONS / "enter_number_activations_for_voucher.png",
    "successful_create_voucher": UI_SECTIONS / "successful_create_voucher.png",
    "successfully_activate_voucher": UI_SECTIONS / "successfully_activate_voucher.png",
    "unsuccessfully_activate_voucher": UI_SECTIONS / "unsuccessfully_activate_voucher.png",
    "viewing_vouchers": UI_SECTIONS / "viewing_vouchers.png",
    "confirm_deactivate_voucher": UI_SECTIONS / "confirm_deactivate_voucher.png",
    "voucher_successful_deactivate": UI_SECTIONS / "voucher_successful_deactivate.png",

    # Ошибки
    "insufficient_funds": UI_SECTIONS / "insufficient_funds.png", # недостаточно средств
    "incorrect_data_entered": UI_SECTIONS / "incorrect_data_entered.png",
    "user_no_found": UI_SECTIONS / "user_no_found.png",
    "server_error": UI_SECTIONS / "server_error.png",

    # Пополнение
    "show_all_services_replenishments": UI_SECTIONS / "show_all_services_replenishments.png",
    "request_enter_amount": UI_SECTIONS / "request_enter_amount.png",
    "pay": UI_SECTIONS / "pay.png", # успешная оплата при пополнении

    # каталог
    "main_catalog": UI_SECTIONS / "main_catalog.png",
    "account_catalog": UI_SECTIONS / "account_catalog.png",
    "confirm_purchase": UI_SECTIONS / "confirm_purchase.png",
    "successful_purchase": UI_SECTIONS / "successful_purchase.png",

    # промокод
    "entering_promo_code": UI_SECTIONS / "entering_promo_code.png",

    # аккаунты
    "purchased_accounts": UI_SECTIONS / "purchased_accounts.png",

}
