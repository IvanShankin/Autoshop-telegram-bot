from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel


class UpdateUserDTO(BaseModel):
    username: Optional[str] = None
    language: Optional[str] = None
    balance: Optional[int] = None
    total_sum_replenishment: Optional[int] = None
    total_profit_from_referrals: Optional[int] = None
    last_used: Optional[datetime] = None


class UpdateNotificationSettingDTO(BaseModel):
    referral_invitation: Optional[bool] = None
    referral_replenishment: Optional[bool] = None


class UpdateReplenishment(BaseModel):
    status: Optional[str] = None
    payment_system_id: Optional[str] = None
    invoice_url: Optional[str] = None
    expire_at: datetime = None
    payment_data: Optional[Dict[str, Any]] = None