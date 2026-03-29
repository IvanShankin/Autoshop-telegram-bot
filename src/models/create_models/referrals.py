from pydantic import BaseModel


class CreateReferralLevelDTO(BaseModel):
    amount_of_achievement: int
    percent: float


class CreateReferralIncomeDTO(BaseModel):
    replenishment_id: int
    owner_user_id: int
    referral_id: int
    amount: int
    percentage_of_replenishment: int
