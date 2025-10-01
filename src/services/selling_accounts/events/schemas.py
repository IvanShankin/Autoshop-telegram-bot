from typing import Optional, List

from pydantic import BaseModel

class AccountsData(BaseModel):
    id_old_product_account: int
    id_new_sold_account: int
    id_purchase_account: int
    cost_price: int
    purchase_price: int
    net_profit: int

class NewPurchaseAccount(BaseModel):
    user_id: int
    category_id: int
    quantity: int
    amount_purchase: int
    account_movement: List[AccountsData]
    languages: List[str]
    promo_code_id: Optional[int]
    user_balance_before: int
    user_balance_after: int






