from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict

from src.database.models.categories import UniversalMediaType, CategoryTranslation
from src.models.read_models import ProductUniversalFull


class _StartPurchaseProduct(BaseModel):
    purchase_request_id: int
    category_id: int
    promo_code_id: int | None
    translations_category: List[CategoryTranslation]
    original_price_one: int  # Цена на момент покупки (без учёта промокода)
    purchase_price_one: int  # Цена на момент покупки (с учётом промокода)
    cost_price_one: int  # Себестоимость на момент покупки
    total_amount: int  # цена которую заплатил пользователь

    user_balance_before: int
    user_balance_after: int

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PurchaseRequestsDTO(BaseModel):
    purchase_request_id: int
    user_id: int
    promo_code_id: int | None
    quantity: int
    total_amount: int
    status: str
    created_at: datetime


class StartPurchaseUniversal(_StartPurchaseProduct):
    media_type: UniversalMediaType
    full_reserved_products: List[ProductUniversalFull]


class StartPurchaseUniversalOne(_StartPurchaseProduct):
    full_product: ProductUniversalFull
    quantity_products: int