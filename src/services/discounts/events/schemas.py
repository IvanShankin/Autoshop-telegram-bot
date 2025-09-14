from pydantic import BaseModel

class NewActivatePromoCode(BaseModel):
    promo_code_id: int
    user_id: int