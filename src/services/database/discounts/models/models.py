from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, CheckConstraint, Index, text, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.services.database.core.database import Base


class PromoCodes(Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        Index('ix_promo_code_activation', 'activation_code', 'is_valid'),
        CheckConstraint('amount IS NOT NULL OR discount_percentage IS NOT NULL'),
        CheckConstraint('discount_percentage BETWEEN 0 AND 100', name='chk_discount_percentage') # процент скидки
    )

    promo_code_id = Column(Integer, primary_key=True, autoincrement=True,)
    activation_code = Column(String(150), nullable=False) # НЕ уникальный, фильтровать необходимо по is_valid
    min_order_amount = Column(Integer, nullable=False) # минимальная сумма с которой можно применить

    # будет на определённую сумму или процент
    activated_counter = Column(Integer, nullable=False, server_default=text('0')) # количество активаций
    amount = Column(Integer, nullable=True) # сумма скидки
    discount_percentage = Column(Integer, nullable=True,) # процент скидки (может быть Null)

    number_of_activations = Column(Integer, nullable=True) # разрешённое количество активаций (если нет, то бесконечное)
    start_at = Column(DateTime(timezone=True), server_default=func.now())
    expire_at = Column(DateTime(timezone=True), nullable=True)
    is_valid = Column(Boolean, nullable=False, server_default=text('true'))

    promo_code_activated_account = relationship("ActivatedPromoCodes", back_populates="promo_code")
    purchases_accounts = relationship("PurchasesAccounts", back_populates="promo_code")

class ActivatedPromoCodes(Base):
    __tablename__ = "activated_promo_codes"

    activated_promo_code_id = Column(Integer, primary_key=True, autoincrement=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.promo_code_id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    promo_code = relationship("PromoCodes", back_populates="promo_code_activated_account")
    user = relationship("Users", back_populates="promo_code_activated_account")

class Vouchers(Base):
    __tablename__ = "vouchers"
    __table_args__ = (
        Index('ix_vouchers_activation_code', 'activation_code', 'is_valid'),
    )

    voucher_id = Column(Integer, primary_key=True, autoincrement=True)
    creator_id = Column(BigInteger, ForeignKey("users.user_id"))
    is_created_admin = Column(Boolean, nullable=False, server_default=text('false'))

    activation_code = Column(String(150), nullable=False) # НЕ уникальный, фильтровать необходимо по is_valid
    amount = Column(Integer, nullable=False)
    activated_counter = Column(Integer, nullable=False, server_default=text('0')) # количество активаций
    number_of_activations = Column(Integer, nullable=True) # разрешённое количество активаций (если нет, то бесконечное такое доступно только для админов)

    start_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expire_at = Column(DateTime(timezone=True), nullable=True)
    is_valid = Column(Boolean, nullable=False, server_default=text('true'))

    user = relationship("Users", back_populates="vouchers")
    voucher_activations = relationship("VoucherActivations", back_populates="vouchers")

class VoucherActivations(Base):
    __tablename__ = "voucher_activations"

    voucher_activation_id = Column(Integer, primary_key=True, autoincrement=True)
    voucher_id = Column(Integer, ForeignKey("vouchers.voucher_id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vouchers = relationship("Vouchers", back_populates="voucher_activations")
    user = relationship("Users", back_populates="voucher_activations")
