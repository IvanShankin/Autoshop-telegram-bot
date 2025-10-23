from pydantic import BaseModel


class GetAmountData(BaseModel):
    amount: int
    payment_id: int