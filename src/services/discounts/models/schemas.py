from pydantic import BaseModel

from src.services.discounts.models import Vouchers


class SmallVoucher(BaseModel):
    """Хранится в redis"""
    voucher_id: int
    creator_id: int
    amount: int
    activation_code: str
    number_of_activations: int

    @classmethod
    def from_orm_model(cls, voucher: "Vouchers"):
        """orm модель превратит в SmallVoucher"""
        return cls(
            voucher_id=voucher.voucher_id,
            creator_id=voucher.creator_id,
            amount=voucher.amount,
            activation_code=voucher.activation_code,
            number_of_activations=voucher.number_of_activations
        )