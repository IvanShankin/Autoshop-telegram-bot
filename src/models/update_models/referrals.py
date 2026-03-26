from typing import Optional

from pydantic import BaseModel


class UpdateReferralLevelDTO(BaseModel):
    amount_of_achievement: Optional[int] = None
    percent: Optional[float] = None
