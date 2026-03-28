from typing import Optional

from pydantic import BaseModel

from src.database.models.categories import ProductType, AccountServiceType, UniversalMediaType


class UpdateCategory(BaseModel):
    index: Optional[int] = None
    show: Optional[bool] = None
    number_buttons_in_row: Optional[int] = None
    is_product_storage: Optional[bool] = None
    allow_multiple_purchase: Optional[bool] = None
    product_type: Optional[ProductType] = None
    type_account_service: Optional[AccountServiceType] = None
    media_type: Optional[UniversalMediaType] = None
    reuse_product: Optional[bool] = None
    price: Optional[int] = None
    cost_price: Optional[int] = None


class UpdateCategoryTranslationsDTO(BaseModel):
    category_id: int
    language: str
    name: Optional[str] = None
    description: Optional[str] = None