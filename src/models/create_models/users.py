from typing import Optional, Dict

from pydantic import BaseModel


class CreateUserDTO(BaseModel):
    user_id: Optional[int]
    username: Optional[str]
    language: Optional[str] = "ru"


class CreateUserAuditLogDTO(BaseModel):
    action_type: str # любое
    message: str
    details: Optional[Dict] = None


class CreateBannedAccountsDTO(BaseModel):
    reason: str


class CreateWalletTransactionDTO(BaseModel):
    type: str
    amount: int
    balance_before: int
    balance_after: int


class CreateReplenishmentDTO(BaseModel):
    origin_amount_rub: int  # Сумма в рублях без учёта комиссии
    amount_rub: int         # Сумма в рублях с учётом комиссии