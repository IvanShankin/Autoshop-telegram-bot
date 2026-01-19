from src.services.database.categories.actions.action_purchase_account import purchase_accounts
from src.services.database.categories.actions.actions_add import add_translation_in_category, add_category
from src.services.database.categories.actions.actions_delete import delete_category, delete_translate_category
from src.services.database.categories.actions.actions_get import get_categories_by_category_id, \
    get_sold_accounts_by_owner_id, get_quantity_products_in_category, get_categories, \
    get_types_product_where_the_user_has_product, get_purchases
from src.services.database.categories.actions.actions_update import update_category, update_category_translation
from src.services.database.categories.actions.products.accounts.actions_add import add_product_account, \
    add_translation_in_sold_account, add_account_storage, add_sold_account, add_deleted_accounts
from src.services.database.categories.actions.products.accounts.actions_delete import delete_product_account, \
    delete_sold_account, delete_product_accounts_by_category
from src.services.database.categories.actions.products.accounts.actions_get import get_product_account_by_category_id, \
    get_product_account_by_account_id, get_sold_account_by_page, get_sold_accounts_by_account_id, get_tg_account_media, \
    get_all_phone_in_account_storage, get_type_service_account, get_count_sold_account, \
    get_types_account_service_where_the_user_purchase
from src.services.database.categories.actions.products.accounts.actions_update import update_account_storage, \
    update_tg_account_media
from src.services.database.categories.actions.products.universal.actions_get import \
    get_product_universal_by_category_id, get_sold_universal_by_owner_id, get_product_universal_by_product_id, \
    get_sold_universal_by_page, get_count_sold_universal, get_sold_universal_by_universal_id

__all__ = [
    "purchase_accounts",

    'add_translation_in_category',
    'add_category',
    'add_product_account',
    'add_translation_in_sold_account',
    'add_account_storage',
    'add_sold_account',
    'add_deleted_accounts',
    'delete_translate_category',
    'delete_category',
    'delete_product_account',
    'delete_sold_account',
    'update_category',
    'update_category_translation',
    'update_account_storage',
    'update_tg_account_media',
    'get_categories_by_category_id',
    'get_quantity_products_in_category',
    'get_categories',
    'get_product_account_by_category_id',
    'get_product_account_by_account_id',
    'get_sold_accounts_by_owner_id',
    'get_sold_account_by_page',
    'get_sold_accounts_by_account_id',
    'get_tg_account_media',
    'get_all_phone_in_account_storage',
    'get_type_service_account',

    'get_count_sold_account',
    'get_types_product_where_the_user_has_product',
    'get_types_account_service_where_the_user_purchase',

    "delete_product_accounts_by_category",
    "get_purchases",

    'get_product_universal_by_category_id',
    'get_product_universal_by_product_id',
    'get_sold_universal_by_owner_id',
    'get_sold_universal_by_page',
    'get_count_sold_universal',
    'get_sold_universal_by_universal_id',
]

