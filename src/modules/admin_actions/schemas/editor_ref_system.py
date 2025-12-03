from pydantic import BaseModel


class GetNewPersentData(BaseModel):
    ref_lvl_id: int


class GetAchievementAmountData(BaseModel):
    ref_lvl_id: int


class CreateRefLevelData(BaseModel):
    achievement_amount: int