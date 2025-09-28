from typing import Optional
from pydantic import BaseModel, ConfigDict

from src.services.selling_accounts.models import AccountCategories, SoldAccounts

class AccountCategoryFull(BaseModel):
    account_category_id: int
    account_service_id: int
    parent_id: Optional[int]

    name: str
    description: Optional[str]

    index: int
    show: bool
    is_main: bool
    is_accounts_storage: bool

    price_one_account: Optional[int]
    cost_price_one_account: Optional[int]

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_translation(cls, category: "AccountCategories", lang: str, fallback: str | None = None):
        """orm модель превратит в AccountCategoryFull"""
        return cls(
            account_category_id=category.account_category_id,
            account_service_id=category.account_service_id,
            parent_id=category.parent_id,
            index=category.index,
            show=category.show,
            is_main=category.is_main,
            is_accounts_storage=category.is_accounts_storage,
            price_one_account=category.price_one_account,
            cost_price_one_account=category.cost_price_one_account,
            name=category.get_name(lang, fallback),
            description=category.get_description(lang, fallback)
        )


class SoldAccountsFull(BaseModel):
    sold_account_id: int
    owner_id: int
    type_account_service_id: int

    is_valid: bool
    is_deleted: bool

    hash_login: Optional[str]
    hash_password: Optional[str]

    name: str
    description: str

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_translation(cls, account: "SoldAccounts", lang: str, fallback: str | None = None):
        """orm модель превратит в SoldAccountsFull"""
        return cls(
            sold_account_id=account.sold_account_id,
            owner_id=account.owner_id,
            type_account_service_id=account.type_account_service_id,
            is_valid=account.is_valid,
            is_deleted=account.is_deleted,
            hash_login=account.hash_login,
            hash_password=account.hash_password,
            name=account.get_name(lang, fallback),
            description=account.get_description(lang, fallback),
        )

