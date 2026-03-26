from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreateActivatedPromoCode(BaseModel):
    promo_code_id: int
    user_id: int


class CreatePromoCodeDTO(BaseModel):
    code: Optional[str] = None                  # если промокод с данным кодом не занят, то будет создан с ним
    min_order_amount: int = 0                   # минимальная сумма для активации
    amount: Optional[int] = None                # сумма скидки (взаимоисключающая с discount_percentage)
    discount_percentage: Optional[int] = None   # процент скидки (взаимоисключающая с amount)
    number_of_activations: int = 1              # число активаций
    expire_at: Optional[datetime] = None        # годен до (указывать с utc)


class CreateVoucherActivationsDTO(BaseModel):
    voucher_id: int
    user_id: int


class CreateVoucherDTO(BaseModel):
    is_created_admin: bool                  # если создаёт админ
    amount: int
    number_of_activations: Optional[int]
    expire_at: Optional[datetime] = None

