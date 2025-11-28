from pydantic import BaseModel


class SetNewBalanceData(BaseModel):
    target_user_id: int

class IssueBanData(BaseModel):
    target_user_id: int