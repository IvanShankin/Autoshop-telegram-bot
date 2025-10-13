from pydantic import BaseModel

from src.services.discounts.models import Vouchers


class SmallVoucher(BaseModel):
    """Хранится в redis"""
    creator_id: int
    amount: int
    activation_code: str

    @classmethod
    def from_orm_model(cls, voucher: "Vouchers"):
        """orm модель превратит в SmallVoucher"""
        return cls(
            creator_id=voucher.creator_id,
            amount=voucher.amount,
            activation_code=voucher.activation_code
        )