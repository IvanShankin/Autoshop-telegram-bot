from typing import List

from pydantic import BaseModel


class _BaseProductData(BaseModel):
    cost_price: int
    purchase_price: int
    net_profit: int
    purchase_id: int


class _BasePurchase(BaseModel):
    user_id: int
    category_id: int
    amount_purchase: int
    user_balance_before: int
    user_balance_after: int
    product_left: int | str # сколько товаров осталось в категории


class AccountsData(_BaseProductData):
    account_storage_id: int
    new_sold_account_id: int


class UniversalProductData(_BaseProductData):
    universal_storage_id: int
    sold_universal_id: int


class NewPurchaseAccount(_BasePurchase):
    account_movement: List[AccountsData]


class NewPurchaseUniversal(_BasePurchase):
    product_movement: List[UniversalProductData]




