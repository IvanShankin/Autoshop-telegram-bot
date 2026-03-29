from pydantic import BaseModel


class NewReplenishment(BaseModel):
    replenishment_id: int
    user_id: int
    origin_amount: int
    amount: int


class ReplenishmentCompleted(BaseModel):
    user_id: int
    replenishment_id: int
    amount: int
    total_sum_replenishment: int | None
    error: bool
    error_str: str | None
    language: str
    username: str | None


class ReplenishmentFailed(BaseModel):
    user_id: int
    replenishment_id: int
    error_str: str | None
    language: str
    username: str | None
