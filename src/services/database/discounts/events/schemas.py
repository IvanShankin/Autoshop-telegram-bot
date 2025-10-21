from pydantic import BaseModel

class NewActivatePromoCode(BaseModel):
    promo_code_id: int
    user_id: int

class NewActivationVoucher(BaseModel):
    user_id: int
    language: str
    voucher_id: int
    amount: int
    balance_before: int
    balance_after: int