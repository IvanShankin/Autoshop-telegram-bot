from typing import Optional, List

from pydantic import BaseModel

class AccountsData(BaseModel):
    id_account_storage: int
    id_new_sold_account: int
    id_purchase_account: int
    cost_price: int
    purchase_price: int
    net_profit: int

class NewPurchaseAccount(BaseModel):
    user_id: int
    category_id: int
    amount_purchase: int
    account_movement: List[AccountsData]
    user_balance_before: int
    user_balance_after: int
    accounts_left: int # сколько аккаунтов осталось в категории






