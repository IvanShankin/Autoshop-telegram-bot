from datetime import datetime

from pydantic import BaseModel


class NewReplenishment(BaseModel):
    user_id: int
    amount: int
    create_at: datetime
