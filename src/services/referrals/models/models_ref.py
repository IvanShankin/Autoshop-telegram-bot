from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.services.database.database import Base


class Referrals(Base):
    __tablename__ = "referrals"

    # Это ID пользователя, которого пригласили (реферала)
    referral_id = Column(Integer, ForeignKey('users.user_id'), primary_key=True, nullable=False)
    owner_user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True) # Это ID пользователя, который пригласил (владельца)
    level = Column(Integer, nullable=False)

    owner = relationship("Users", foreign_keys=[owner_user_id], back_populates="owned_referrals") # владелец реферала
    referral = relationship("Users", foreign_keys=[referral_id], back_populates="referred_by_link") # реферал

class ReferralLevels(Base):
    __tablename__ = "referral_levels"

    referral_level_id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, nullable=False, unique=True)
    amount_of_achievement = Column(Integer, nullable=False) # сумма с которой достигается
    percent = Column(Integer, nullable=False)

class IncomeFromReferrals(Base):
    __tablename__ = "income_from_referrals"

    income_from_referral_id = Column(Integer, primary_key=True, autoincrement=True)
    replenishment_id = Column(Integer, ForeignKey("replenishments.replenishment_id"), nullable=False)

    # ID пользователя-ВЛАДЕЛЬЦА (того, кто получил доход)
    owner_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    # ID пользователя-РЕФЕРАЛА (с которого был получен доход)
    referral_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)

    amount = Column(Integer, nullable=False)
    percentage_of_replenishment = Column(Integer, nullable=False) # процент от пополнения на момент операции
    date_created = Column(DateTime(timezone=True), server_default=func.now())

    replenishment = relationship("Replenishments", back_populates="income_from_referral")
    owner = relationship("Users", foreign_keys=[owner_user_id], back_populates="income_as_owner") # владелец реферала
    referral = relationship("Users", foreign_keys=[referral_id], back_populates="income_as_referral") # реферал
