from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class ReferralReportItemDTO(BaseModel):
    referral_id: int
    username: Optional[str]
    level: int
    join_date: datetime
    total_income: int


class ReferralIncomeItemDTO(BaseModel):
    deposit_id: int
    referral_id: int
    amount: int
    percentage: float
    created_at: datetime


class ReferralReportDTO(BaseModel):
    referrals: List[ReferralReportItemDTO]
    incomes: List[ReferralIncomeItemDTO]