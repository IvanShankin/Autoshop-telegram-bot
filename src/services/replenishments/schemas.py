from datetime import datetime

from pydantic import BaseModel


class NewReplenishment(BaseModel):
    replenishment_id: int
    user_id: int
    amount: int
    create_at: datetime

class ReplenishmentCompleted(BaseModel):
    user_id: int
    replenishment_id: int
    amount: int # сумма пополнения
    total_sum_replenishment: int | None# сколько всего данный пользователь пополнил
    error: bool # флаг ошибки
    error_str: str | None # данные об ошибке
    language: str # выбранный язык пользователя
    username: str

class ReplenishmentFailed(BaseModel):
    user_id: int
    replenishment_id: int
    error_str: str | None # данные об ошибке
    language: str # выбранный язык пользователя
    username: str