from src.repository.database.categories.category import CategoriesRepository
from src.repository.database.categories.category_translations import CategoryTranslationsRepository
from src.repository.database.categories.purchases import PurchasesRepository
from src.repository.database.categories.purchase_requests import PurchaseRequestsRepository
from src.repository.database.categories.purchase_request_accounts import PurchaseRequestAccountsRepository
from src.repository.database.categories.purchase_request_universal import PurchaseRequestUniversalRepository

from src.repository.database.categories.accounts.deleted_accounts import DeletedAccountsRepository
from src.repository.database.categories.accounts.product_accounts import ProductAccountsRepository
from src.repository.database.categories.accounts.sold_accounts import SoldAccountsRepository
from src.repository.database.categories.accounts.sold_accounts_translate import SoldAccountsTranslationRepository
from src.repository.database.categories.accounts.storage_accounts import AccountStorageRepository
from src.repository.database.categories.accounts.tg_accounts_media import TgAccountMediaRepository

from src.repository.database.categories.universal.delete_universal import DeletedUniversalRepository
from src.repository.database.categories.universal.product_universal import ProductUniversalRepository
from src.repository.database.categories.universal.sold_universal import SoldUniversalRepository
from src.repository.database.categories.universal.universal_storage import UniversalStorageRepository
from src.repository.database.categories.universal.universal_translation import UniversalTranslationRepository


__all__ = [
    "CategoriesRepository",
    "CategoryTranslationsRepository",
    "PurchasesRepository",
    "PurchaseRequestsRepository",
    "PurchaseRequestAccountsRepository",
    "PurchaseRequestUniversalRepository",

    "DeletedAccountsRepository",
    "ProductAccountsRepository",
    "SoldAccountsRepository",
    "SoldAccountsTranslationRepository",
    "AccountStorageRepository",
    "TgAccountMediaRepository",

    "DeletedUniversalRepository",
    "ProductUniversalRepository",
    "SoldUniversalRepository",
    "UniversalStorageRepository",
    "UniversalTranslationRepository",
]
