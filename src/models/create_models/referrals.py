from pydantic import BaseModel


class CreateReferralLevelDTO(BaseModel):
    amount_of_achievement: int
    percent: float
