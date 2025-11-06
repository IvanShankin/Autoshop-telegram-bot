from typing import List
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from src.services.database.selling_accounts.models import SoldAccounts, ProductAccounts
from src.services.database.selling_accounts.models.models import AccountStorage, AccountCategories, \
    AccountCategoryTranslation


class PurchaseAccountSchem(BaseModel):
    ids_deleted_product_account: List[int]
    ids_new_sold_account: List[int]

class StartPurchaseAccount(BaseModel):
    purchase_request_id: int
    category_id: int
    type_account_service_id: int
    promo_code_id: int | None
    product_accounts: List[ProductAccounts] # ОБЯЗАТЕЛЬНО с подгруженными AccountStorage
    type_service_name: str
    translations_category: List[AccountCategoryTranslation]
    original_price_one_acc: int  # Цена на момент покупки (без учёта промокода)
    purchase_price_one_acc: int  # Цена на момент покупки (с учётом промокода)
    cost_price_one_acc: int  # Себестоимость на момент покупки
    total_amount: int  # цена которую заплатил пользователь

    user_balance_before: int
    user_balance_after: int


    model_config = ConfigDict(arbitrary_types_allowed=True)

class AccountCategoryFull(BaseModel):
    account_category_id: int
    account_service_id: int
    ui_image_key: str
    parent_id: Optional[int]

    name: str
    description: Optional[str]

    index: int
    show: bool
    number_buttons_in_row: int
    is_main: bool
    is_accounts_storage: bool

    price_one_account: Optional[int]
    cost_price_one_account: Optional[int]

    # Число аккаунтов на продаже которое хранит в себе. Есть только у категорий хранящие аккаунты
    quantity_product_account: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_translation(
            cls,
            category: AccountCategories,
            quantity_product_account:int,
            lang: str,
            fallback: str | None = None
        ):
        """orm модель превратит в AccountCategoryFull"""
        return cls(
            account_category_id=category.account_category_id,
            account_service_id=category.account_service_id,
            ui_image_key=category.ui_image_key,
            parent_id=category.parent_id,
            index=category.index,
            show=category.show,
            number_buttons_in_row=category.number_buttons_in_row,
            is_main=category.is_main,
            is_accounts_storage=category.is_accounts_storage,
            price_one_account=category.price_one_account,
            cost_price_one_account=category.cost_price_one_account,
            name=category.get_name(lang, fallback),
            description=category.get_description(lang, fallback),
            quantity_product_account=quantity_product_account
        )

class AccountStoragePydentic(BaseModel):
    account_storage_id: int
    storage_uuid: str

    file_path: str
    checksum: str

    encrypted_key: str
    encrypted_key_nonce: str
    key_version: int
    encryption_algo: str

    login_encrypted: Optional[str] = None
    password_encrypted: Optional[str] = None

    is_active: bool
    is_valid: bool

    added_at: datetime
    last_check_at: Optional[datetime] = None


class ProductAccountSmall(BaseModel):
    account_id: int
    type_account_service_id: int
    account_category_id: int
    account_storage_id: int
    created_at: datetime

    @classmethod
    def from_orm_model(cls, product_account: ProductAccounts):
        """orm модель превратит в ProductAccountSmall"""
        return cls(
            account_id=product_account.account_id,
            type_account_service_id=product_account.type_account_service_id,
            account_category_id=product_account.account_category_id,
            created_at=product_account.created_at,
            account_storage_id=product_account.account_storage_id
        )


class ProductAccountFull(BaseModel):
    account_id: int
    type_account_service_id: int
    account_category_id: int
    created_at: datetime

    account_storage: AccountStoragePydentic

    @classmethod
    def from_orm_model(cls, product_account: ProductAccounts, storage_account: AccountStorage):
        """orm модель превратит в ProductAccountFull"""
        return cls(
            account_id=product_account.account_id,
            type_account_service_id=product_account.type_account_service_id,
            account_category_id=product_account.account_category_id,
            created_at=product_account.created_at,
            account_storage= AccountStoragePydentic(**storage_account.to_dict()),
        )



class SoldAccountFull(BaseModel):
    sold_account_id: int
    owner_id: int
    type_account_service_id: int

    name: str
    description: str

    sold_at: datetime

    account_storage: AccountStoragePydentic

    @classmethod
    async def from_orm_with_translation(cls, account: SoldAccounts, lang: str, fallback: str | None = None):
        """orm модель превратит в SoldAccountsFull"""
        return cls(
            sold_account_id=account.sold_account_id,
            owner_id=account.owner_id,
            type_account_service_id=account.type_account_service_id,
            name=account.get_name(lang, fallback),
            description=account.get_description(lang, fallback),
            sold_at=account.sold_at,
            account_storage=AccountStoragePydentic(**account.account_storage.to_dict())
        )

class SoldAccountSmall(BaseModel):
    sold_account_id: int
    owner_id: int
    type_account_service_id: int

    name: str
    description: str

    sold_at: datetime

    @classmethod
    def from_orm_with_translation(cls, account: SoldAccounts, lang: str, fallback: str | None = None):
        """orm модель превратит в SoldAccountSmall"""
        return cls(
            sold_account_id=account.sold_account_id,
            owner_id=account.owner_id,
            type_account_service_id=account.type_account_service_id,
            name=account.get_name(lang, fallback),
            description=account.get_description(lang, fallback),
            sold_at=account.sold_at,
        )