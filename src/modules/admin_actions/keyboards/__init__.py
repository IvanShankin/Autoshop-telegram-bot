from src.modules.admin_actions.keyboards.editors.editor_kb import choice_editor_kb, back_in_choice_editor_kb
from src.modules.admin_actions.keyboards.editors.images_kb import images_list_kb, image_editor, back_in_image_editor
from src.modules.admin_actions.keyboards.editors.mass_mailing_kb import admin_mailing_kb, back_in_admin_mailing_kb, \
    editor_message_mailing_kb, change_mailing_photo_kb, change_mailing_text_kb, change_mailing_btn_url_kb, \
    all_admin_mass_mailing_kb, show_sent_mass_message_kb, back_in_editor_mes_mailing_kb
from src.modules.admin_actions.keyboards.keyboard_main import main_admin_kb, back_in_main_admin_kb
from src.modules.admin_actions.keyboards.editors.promo_codes_kb import admin_promo_kb, all_admin_promo_kb, \
    select_promo_code_type_kb, skip_number_activations_promo_or_in_start_kb, skip_expire_at_promo_or_in_start_kb, \
    show_admin_promo_kb, in_show_admin_promo_kb, confirm_deactivate_promo_code_kb, back_in_all_admin_promo_kb, \
    back_in_admin_promo_kb, back_in_start_creating_promo_code_kb
from src.modules.admin_actions.keyboards.editors.category_kb import show_category_admin_kb, change_category_data_kb, \
    select_lang_category_kb, name_or_description_kb, delete_category_kb, delete_product_kb, \
    back_in_category_update_data_kb, \
    back_in_category_kb, in_category_editor_kb
from src.modules.admin_actions.keyboards.settings_kb import admin_settings_kb, back_in_admin_settings_kb, \
    change_admin_settings_kb, back_in_change_admin_settings_kb
from src.modules.admin_actions.keyboards.show_data_kb import data_by_id_by_page_kb, back_in_show_data_by_id_kb
from src.modules.admin_actions.keyboards.user_management_kb import user_management_kb, back_in_user_management_kb, \
    confirm_remove_ban_kb

from src.modules.admin_actions.keyboards.editors.vouchers_kb import admin_vouchers_kb, skip_expire_at_or_back_kb, \
    all_admin_vouchers_kb, skip_number_activations_or_back_kb, in_admin_voucher_kb, show_admin_voucher_kb, \
    back_in_all_admin_voucher_kb, confirm_deactivate_admin_voucher_kb, back_in_admin_vouchers_kb, \
    back_in_start_creating_admin_vouchers_kb

__all__ = [
    "in_category_editor_kb",
    "show_category_admin_kb",
    "change_category_data_kb",
    "select_lang_category_kb",
    "name_or_description_kb",
    "delete_product_kb",
    "delete_category_kb",
    "back_in_category_update_data_kb",
    "back_in_category_kb",
    "choice_editor_kb",
    "back_in_choice_editor_kb",
    "user_management_kb",
    "back_in_user_management_kb",
    "confirm_remove_ban_kb",
    "main_admin_kb",
    "back_in_main_admin_kb",
    "images_list_kb",
    "image_editor",
    "back_in_image_editor",

    # ваучеры
    "admin_vouchers_kb",
    "skip_number_activations_or_back_kb",
    "skip_expire_at_or_back_kb",
    "all_admin_vouchers_kb",
    "show_admin_voucher_kb",
    "in_admin_voucher_kb",
    "back_in_all_admin_voucher_kb",
    "confirm_deactivate_admin_voucher_kb",
    "back_in_admin_vouchers_kb",
    "back_in_start_creating_admin_vouchers_kb",

    # промокоды
    "admin_promo_kb",
    "all_admin_promo_kb",
    "select_promo_code_type_kb",
    "skip_number_activations_promo_or_in_start_kb",
    "skip_expire_at_promo_or_in_start_kb",
    "show_admin_promo_kb",
    "in_show_admin_promo_kb",
    "confirm_deactivate_promo_code_kb",
    "back_in_all_admin_promo_kb",
    "back_in_admin_promo_kb",
    "back_in_start_creating_promo_code_kb",

    # массовая рассылка
    "admin_mailing_kb",
    "editor_message_mailing_kb",
    "change_mailing_photo_kb",
    "change_mailing_text_kb",
    "change_mailing_btn_url_kb",
    "all_admin_mass_mailing_kb",
    "show_sent_mass_message_kb",
    "back_in_editor_mes_mailing_kb",
    "back_in_admin_mailing_kb",

    # просмотр по ID
    "data_by_id_by_page_kb",
    "back_in_show_data_by_id_kb",

    # настройки
    "admin_settings_kb",
    "change_admin_settings_kb",
    "back_in_change_admin_settings_kb",
    "back_in_admin_settings_kb",
]