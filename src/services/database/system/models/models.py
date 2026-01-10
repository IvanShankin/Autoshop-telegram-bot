from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, BigInteger, text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.services.database.core.database import Base

class Settings(Base):
    __tablename__ = "settings"

    settings_id = Column(Integer, primary_key=True, autoincrement=True)
    maintenance_mode = Column(Boolean, nullable=True, server_default=text("false"))
    support_username = Column(String(200), nullable=True)           # хранит просто текст, без @
    channel_for_logging_id = Column(BigInteger, nullable=True)      # ID канала для логирования
    channel_for_subscription_id = Column(BigInteger, nullable=True) # ID канала для подписки пользователя
    channel_for_subscription_url = Column(String(300), nullable=True) # опционально
    channel_name = Column(Text, nullable=True)
    shop_name = Column(Text, nullable=True)
    FAQ = Column(Text, nullable=True) # ссылка

class UiImages(Base):
    __tablename__ = "ui_images"

    key = Column(String(300), primary_key=True)
    file_path = Column(Text, nullable=False) # полный путь
    file_id = Column(Text, nullable=True)
    show = Column(Boolean, nullable=False, server_default=text('true'))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    category = relationship("Categories", back_populates="ui_image")
    message_for_sending = relationship("MessageForSending", back_populates="ui_image")


class TypePayments(Base):
    __tablename__ = "type_payments"

    type_payment_id = Column(Integer, primary_key=True, autoincrement=True)
    # у админа будет собственное название (только для него в панели администратора)
    name_for_user = Column(String(200), nullable=False)  # Название метода (CryptoBot, ЮMoney и т.д.)
    # name_for_admin мы устанавливаем сами, админ не может поменять (значения берутся с переменной get_config().app.type_payments)
    name_for_admin = Column(String(200), nullable=False, index=True)
    is_active = Column(Boolean, server_default=text('true'))  # Активен ли метод
    commission = Column(Float, default=0)  # Комиссия в процентах
    index = Column(Integer, nullable=False)
    extra_data = Column(JSON, nullable=True)  # Дополнительные параметры метода

    replenishments = relationship("Replenishments", back_populates="type_payment")

class BackupLogs(Base):
    __tablename__ = "backup_logs"

    backup_log_id = Column(Integer, primary_key=True, autoincrement=True)

    # имя объекта в storage service
    storage_file_name = Column(String(512), nullable=False, unique=True)
    storage_encrypted_dek_name = Column(String(512), nullable=False, unique=True)

    # DEK
    encrypted_dek_b64 = Column(Text, nullable=False)
    dek_nonce_b64 = Column(String(64), nullable=False)

    size_bytes = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
