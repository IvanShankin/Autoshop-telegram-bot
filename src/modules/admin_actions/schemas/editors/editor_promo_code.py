from datetime import datetime

from pydantic import BaseModel


class CreatePromoCodeData(BaseModel):
    amount: int | None = None
    discount_percentage: int | None = None
    number_of_activations: int | None = None
    expire_at: datetime | None = None
    min_order_amount: int
