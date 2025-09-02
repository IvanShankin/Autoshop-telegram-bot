from datetime import datetime

from pydantic import BaseModel


class NewReplenishment(BaseModel):
    replenishment_id: int
    user_id: int
    amount: int
    create_at: datetime
