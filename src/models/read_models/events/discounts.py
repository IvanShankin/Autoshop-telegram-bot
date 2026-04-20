from pydantic import BaseModel

from src.models.read_models.other import VouchersDTO


class NewActivatePromoCode(BaseModel):
    promo_code_id: int
    user_id: int

class NewActivationVoucher(BaseModel):
    voucher: VouchersDTO