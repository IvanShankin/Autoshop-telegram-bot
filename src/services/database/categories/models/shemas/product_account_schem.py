from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from src.services.database.categories.models import SoldAccounts, ProductAccounts
from src.services.database.categories.models import AccountStorage, Categories
from src.services.database.categories.models.main_category_and_product import ProductType
from src.services.database.categories.models.product_account import AccountServiceType


class CategoryFull(BaseModel):
    category_id: int
    ui_image_key: str
    parent_id: Optional[int]

    language: str
    name: str
    description: Optional[str]

    index: int
    show: bool
    number_buttons_in_row: int

    is_main: bool
    is_product_storage: bool
    allow_multiple_purchase: bool # разрешена продажа одного товара много раз

    product_type: ProductType | None
    type_account_service: AccountServiceType | None
    reuse_product: bool | None
    price: int | None
    cost_price: int | None

    # Число товаров на продаже которое хранит в себе. Есть только у категорий хранящие продукты
    quantity_product: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_translation(
            cls,
            category: Categories,
            quantity_product:int,
            lang: str,
            fallback: str | None = None
        ):
        """orm модель превратит в CategoryFull"""
        return cls(
            category_id=category.category_id,
            ui_image_key=category.ui_image_key,
            parent_id=category.parent_id,
            index=category.index,
            show=category.show,
            number_buttons_in_row=category.number_buttons_in_row,
            is_main=category.is_main,

            language=lang,
            name=category.get_name(lang, fallback),
            description=category.get_description(lang, fallback),

            is_product_storage=category.is_product_storage,
            allow_multiple_purchase=category.allow_multiple_purchase,

            product_type=category.product_type,
            type_account_service=category.type_account_service,
            reuse_product=category.reuse_product,
            price=category.price,
            cost_price=category.cost_price,

            quantity_product=quantity_product,
        )


class AccountStoragePydantic(BaseModel):
    account_storage_id: int
    storage_uuid: str

    file_path: str
    checksum: str
    status: str

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


class ProductAccountSmall(BaseModel):
    account_id: int
    type_account_service: AccountServiceType
    category_id: int
    account_storage_id: int
    created_at: datetime

    @classmethod
    def from_orm_model(cls, product_account: ProductAccounts):
        """orm модель превратит в ProductAccountSmall"""
        return cls(
            account_id=product_account.account_id,
            type_account_service=product_account.type_account_service,
            category_id=product_account.category_id,
            created_at=product_account.created_at,
            account_storage_id=product_account.account_storage_id
        )


class ProductAccountFull(BaseModel):
    account_id: int
    category_id: int
    type_account_service: AccountServiceType
    created_at: datetime

    account_storage: AccountStoragePydantic

    @classmethod
    def from_orm_model(cls, product_account: ProductAccounts, storage_account: AccountStorage):
        """orm модель превратит в ProductAccountFull"""
        return cls(
            account_id=product_account.account_id,
            category_id=product_account.category_id,
            type_account_service=product_account.type_account_service,
            created_at=product_account.created_at,
            account_storage=AccountStoragePydantic(**storage_account.to_dict()),
        )


class SoldAccountFull(BaseModel):
    sold_account_id: int
    owner_id: int
    type_account_service: AccountServiceType

    name: str
    description: str | None

    sold_at: datetime

    account_storage: AccountStoragePydantic

    @classmethod
    def from_orm_with_translation(cls, account: SoldAccounts, lang: str, fallback: str | None = None):
        """orm модель превратит в SoldAccountsFull"""
        return cls(
            sold_account_id=account.sold_account_id,
            owner_id=account.owner_id,
            type_account_service=account.type_account_service,
            name=account.get_name(lang, fallback),
            description=account.get_description(lang, fallback),
            sold_at=account.sold_at,
            account_storage=AccountStoragePydantic(**account.account_storage.to_dict())
        )


class SoldAccountSmall(BaseModel):
    sold_account_id: int
    owner_id: int
    type_account_service: AccountServiceType

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
            type_account_service=account.type_account_service,
            name=account.get_name(lang, fallback),
            description=account.get_description(lang, fallback),
            sold_at=account.sold_at,
            phone_number=account.account_storage.phone_number
        )