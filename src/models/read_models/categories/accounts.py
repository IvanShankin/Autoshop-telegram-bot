from typing import Optional
from datetime import datetime

from src.database.models.categories import SoldAccounts, ProductAccounts
from src.database.models.categories import AccountStorage
from src.database.models.categories.main_category_and_product import AccountServiceType, StorageStatus
from src.models.base import ORMDTO


class SoldAccountsDTO(ORMDTO):
    sold_account_id: int
    owner_id: int | None
    account_storage_id: int
    sold_at: datetime


class SoldAccountsTranslationDTO(ORMDTO):
    sold_account_translations_id: int
    sold_account_id: int
    lang: str
    name: str
    description: str | None


class TgAccountMediaDTO(ORMDTO):
    tg_account_media_id: int
    account_storage_id: int
    tdata_tg_id: str | None
    session_tg_id: str | None


class DeletedAccountsDTO(ORMDTO):
    deleted_account_id: int
    account_storage_id: int
    category_name: str
    description: str | None
    create_at: datetime


class AccountStorageDTO(ORMDTO):
    account_storage_id: int
    storage_uuid: str

    is_file: bool
    checksum: str
    status: StorageStatus
    type_account_service: AccountServiceType

    encrypted_key: str
    encrypted_key_nonce: str
    key_version: int
    encryption_algo: str

    tg_id: int | None
    phone_number: str
    login_encrypted: Optional[str] = None
    login_nonce: Optional[str] = None
    password_encrypted: Optional[str] = None
    password_nonce: Optional[str] = None

    is_active: bool
    is_valid: bool

    added_at: datetime
    last_check_at: Optional[datetime] = None


class ProductAccountSmall(ORMDTO):
    account_id: int
    category_id: int
    account_storage_id: int
    created_at: datetime

    @classmethod
    def from_orm_model(cls, product_account: ProductAccounts):
        """orm модель превратит в ProductAccountSmall"""
        return cls(
            account_id=product_account.account_id,
            category_id=product_account.category_id,
            created_at=product_account.created_at,
            account_storage_id=product_account.account_storage_id
        )


class ProductAccountFull(ORMDTO):
    account_id: int
    category_id: int
    account_storage_id: int
    created_at: datetime

    account_storage: AccountStorageDTO

    @classmethod
    def from_orm_model(cls, product_account: ProductAccounts, storage_account: AccountStorage):
        """orm модель превратит в ProductAccountFull"""
        return cls(
            account_id=product_account.account_id,
            category_id=product_account.category_id,
            account_storage_id=product_account.account_storage_id,
            created_at=product_account.created_at,
            account_storage=AccountStorageDTO(**storage_account.to_dict()),
        )


class SoldAccountFull(ORMDTO):
    sold_account_id: int
    owner_id: int

    name: str
    description: str | None

    sold_at: datetime

    account_storage: AccountStorageDTO

    @classmethod
    def from_orm_with_translation(cls, account: SoldAccounts, lang: str, fallback: str | None = None):
        """orm модель превратит в SoldAccountsFull"""
        return cls(
            sold_account_id=account.sold_account_id,
            owner_id=account.owner_id,
            name=account.get_name(lang, fallback),
            description=account.get_description(lang, fallback),
            sold_at=account.sold_at,
            account_storage=AccountStorageDTO(**account.account_storage.to_dict())
        )


class SoldAccountSmall(ORMDTO):
    sold_account_id: int
    owner_id: int

    phone_number: str
    name: str
    description: str | None

    sold_at: datetime

    @classmethod
    def from_orm_with_translation(cls, account: SoldAccounts, lang: str, fallback: str | None = None):
        """orm модель превратит в SoldAccountSmall. SoldAccounts передавать обязательно с подгруженным account_storage"""
        return cls(
            sold_account_id=account.sold_account_id,
            owner_id=account.owner_id,
            name=account.get_name(lang, fallback),
            description=account.get_description(lang, fallback),
            sold_at=account.sold_at,
            phone_number=account.account_storage.phone_number
        )