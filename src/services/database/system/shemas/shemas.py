from datetime import datetime
from typing import List

from pydantic import BaseModel


class ReplenishmentPaymentSystem(BaseModel):
    name: str
    quantity_replenishments: int
    amount_replenishments: int


class StatisticsData(BaseModel):
    active_users: int
    new_users: int
    total_users: int

    quantity_sale_accounts: int
    amount_sale_accounts: int
    total_net_profit: int

    quantity_replenishments: int
    amount_replenishments: int
    replenishment_payment_systems: List[ReplenishmentPaymentSystem] # тут все переменные с TYPE_PAYMENTS

    funds_in_bot: int # средств в боте всего (по выставленной цене)
    accounts_for_sale: int # аккаунтов на продаже

    last_backup: str
