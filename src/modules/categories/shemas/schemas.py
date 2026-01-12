from pydantic import BaseModel


class BuyProductsData(BaseModel):
    quantity_for_buying: int = 0
    old_message_id: int = 0
    category_id: int = 0
    promo_code_id: int | None = None
    promo_code: str | None = None
    promo_code_amount: int | None = None # не None если есть promo_code
    discount_percentage: int | None = None # не None если есть promo_code