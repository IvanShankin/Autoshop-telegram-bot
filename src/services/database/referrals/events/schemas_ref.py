from pydantic import BaseModel

class NewIncomeFromRef(BaseModel):
    referral_id: int
    replenishment_id: int
    owner_id: int
    amount: int
    total_sum_replenishment: int