from pydantic import ConfigDict

from src.services.database.categories.models import ProductAccounts
from src.services.database.categories.models.product_account import AccountServiceType
from typing import List
from pydantic import BaseModel
from src.services.database.categories.models import CategoryFull, CategoryTranslation
from src.services.database.categories.models.product_universal import UniversalMediaType
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull


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


class StartPurchaseAccount(_StartPurchaseProduct):
    type_service_account: AccountServiceType
    product_accounts: List[ProductAccounts] # ОБЯЗАТЕЛЬНО с подгруженными AccountStorage


class StartPurchaseUniversal(_StartPurchaseProduct):
    media_type: UniversalMediaType
    full_reserved_products: List[ProductUniversalFull]


class StartPurchaseUniversalOne(_StartPurchaseProduct):
    full_product: ProductUniversalFull
    quantity_products: int


class PurchaseAccountSchema(BaseModel):
    ids_deleted_product_account: List[int]
    ids_new_sold_account: List[int]


class ResultCheckCategory(BaseModel):
    category: CategoryFull
    translations_category: List[CategoryTranslation]
    final_total: int     # конечная сумма которую должен заплатить пользователь
    user_balance_before: int

    model_config = ConfigDict(arbitrary_types_allowed=True)