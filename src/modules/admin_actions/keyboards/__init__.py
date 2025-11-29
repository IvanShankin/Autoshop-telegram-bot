from src.modules.admin_actions.keyboards.editor_kb import choice_editor_kb
from src.modules.admin_actions.keyboards.keyboard_main import main_admin_kb, back_in_main_admin_kb
from src.modules.admin_actions.keyboards.service_kb import all_services_account_admin_kb, show_service_acc_admin_kb, \
    all_services_types_kb, to_services_kb, delete_service_kb, back_in_service_kb
from src.modules.admin_actions.keyboards.category_kb import show_account_category_admin_kb, change_category_data_kb, \
    select_lang_category_kb, name_or_description_kb, delete_accounts_kb, delete_category_kb, back_in_category_update_data_kb, \
    back_in_category_kb
from src.modules.admin_actions.keyboards.settings_kb import admin_settings_kb, back_in_admin_set_kb
from src.modules.admin_actions.keyboards.user_management_kb import user_management_kb, back_in_user_management_kb, \
    confirm_remove_ban_kb

__all__ = [
    "all_services_account_admin_kb",
    "show_service_acc_admin_kb",
    "all_services_types_kb",
    "to_services_kb",
    "delete_service_kb",
    "back_in_service_kb",
    "show_account_category_admin_kb",
    "change_category_data_kb",
    "select_lang_category_kb",
    "name_or_description_kb",
    "delete_accounts_kb",
    "delete_category_kb",
    "back_in_category_update_data_kb",
    "back_in_category_kb",
    "back_in_admin_set_kb",
    "choice_editor_kb",
    "user_management_kb",
    "back_in_user_management_kb",
    "confirm_remove_ban_kb",
    "main_admin_kb",
    "back_in_main_admin_kb",
]