from pydantic import BaseModel


class ReferralReplenishmentCompleted(BaseModel):
    user_id: int
    replenishment_id: int
    amount: int
    total_sum_replenishment: int | None


class ReferralIncomeResult(BaseModel):
    owner_user_id: int
    owner_language: str
    referral_id: int
    replenishment_id: int
    replenishment_amount: int
    income_amount: int
    last_level: int
    current_level: int
    percent: float
