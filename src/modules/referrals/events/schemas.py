from datetime import datetime
from pydantic import BaseModel

class NewIncomeFromRef(BaseModel):
    referral_id: int
    replenishment_id: int
    owner_id: int
    balance_before_repl: int # баланс до пополнения
    amount: int