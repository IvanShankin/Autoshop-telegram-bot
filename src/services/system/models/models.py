from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, BigInteger, text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.services.database.database import Base

class Settings(Base):
    __tablename__ = "settings"

    settings_id = Column(Integer, primary_key=True, autoincrement=True)
    support_username = Column(String(200), nullable=True)
    hash_token_logger_bot = Column(Text, nullable=True) # токен для бота логера
    channel_for_logging_id = Column(BigInteger, nullable=True)   # ID канала для логирования
    channel_for_subscription_id = Column(BigInteger, nullable=True)   # ID канала для подписки пользователя
    FAQ = Column(Text, nullable=True) # ссылка

class UiImages(Base):
    __tablename__ = "ui_images"

    key = Column(String(100), primary_key=True)
    file_path = Column(String(300), nullable=False)
    show = Column(Boolean, nullable=False, server_default=text('true'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TypePayments(Base):
    __tablename__ = "type_payments"

    type_payment_id = Column(Integer, primary_key=True, autoincrement=True)
    # у админа будет собственное название (только для него в панели администратора)
    name_for_user = Column(String(400), nullable=False)  # Название метода (CryptoBot, ЮMoney и т.д.)
    name_for_admin = Column(String(400), nullable=False) # это мы устанавливаем сами, админ не может поменять
    is_active = Column(Boolean, server_default=text('true'))  # Активен ли метод
    commission = Column(Float, default=0)  # Комиссия в процентах
    index = Column(Integer, nullable=False)
    extra_data = Column(JSON, nullable=True)  # Дополнительные параметры метода

    replenishments = relationship("Replenishments", back_populates="type_payment")

class BackupLogs(Base):
    __tablename__ = "backup_logs"

    backup_log_id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    size_in_kilobytes = Column(Integer, nullable=False)