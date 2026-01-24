import enum
from typing import Callable, Any

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Index, text, UniqueConstraint, \
    inspect, BigInteger, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.services.database.core.database import Base


class AccountServiceType(enum.Enum):
    TELEGRAM = "telegram"
    OTHER = "other"


class AccountStorage(Base):
    """
    Универсальное хранилище данных аккаунта.
    Все состояния (продажа, продан, удалён) ссылаются на него.
    """
    __tablename__ = "account_storage"

    account_storage_id = Column(Integer, primary_key=True, autoincrement=True)
    # UUID, используется в структуре папок (accounts/for_sale/telegram/<uuid>/)
    storage_uuid = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))

    # === Основные поля ===
    file_path = Column(Text, nullable=True)     # относительный путь к зашифрованному файлу (относительно accounts/)
    checksum = Column(String(64), nullable=False) # Контроль целостности (SHA256 зашифрованного файла)
    status = Column(Enum('for_sale', 'reserved', 'bought', 'deleted', name='account_status'), server_default='for_sale')

    # === Шифрование ===
    encrypted_key = Column(Text, nullable=False)       # Персональный ключ аккаунта, зашифрованный мастер-ключом (base64)
    encrypted_key_nonce = Column(Text, nullable=False)  # nonce, использованный при wrap (Nonce (IV) для AES-GCM (base64))
    key_version = Column(Integer, nullable=False, server_default=text("1")) # Номер мастер-ключа (для ротации)
    encryption_algo = Column(String(32), nullable=False, server_default=text("'AES-GCM-256'")) # Алгоритм шифрования

    # === Основные поля ===
    phone_number = Column(String(100), nullable=False) # Пример: +79161234567
    login_encrypted = Column(Text, nullable=True)
    login_nonce = Column(Text, nullable=True)
    password_encrypted = Column(Text, nullable=True)
    password_nonce = Column(Text, nullable=True)

    # === Флаги ===
    is_active = Column(Boolean, nullable=False, server_default=text('true')) # логическое удаление
    is_valid = Column(Boolean, nullable=False, server_default=text('true'))  # валидный или нет

    # === Таймштампы ===
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    last_check_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())  # последняя проверка

    # связи
    product_account = relationship("ProductAccounts", back_populates="account_storage", cascade="all, delete-orphan", uselist=False)
    sold_account = relationship("SoldAccounts", back_populates="account_storage", cascade="all, delete-orphan", uselist=False)
    deleted_account = relationship("DeletedAccounts", back_populates="account_storage", cascade="all, delete-orphan", uselist=False)
    purchase_request_accounts = relationship("PurchaseRequestAccount", back_populates="account_storage", uselist=False)
    purchase = relationship("Purchases", back_populates="account_storage", uselist=False)
    tg_account_media = relationship("TgAccountMedia", back_populates="account_storage", cascade="all, delete-orphan", uselist=False)


class TgAccountMedia(Base):
    """
    Хранит ID файлов в телеграмме (tdata, .session) которое отправляли ранее.

    Названия столбцов связаны в функции по отправке данных пользователю (get_file_for_login)
    """
    __tablename__ = "tg_account_media"

    tg_account_media_id = Column(Integer, primary_key=True, autoincrement=True)
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)
    tdata_tg_id = Column(String(500), nullable=True)
    session_tg_id = Column(String(500), nullable=True)

    account_storage = relationship("AccountStorage", back_populates="tg_account_media")


class ProductAccounts(Base):
    """Хранит записи об аккаунтах которые стоят на продаже, если аккаунт продан, здесь запись удаляется"""
    __tablename__ = "product_accounts"

    account_id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(ForeignKey("categories.category_id"), nullable=False)
    type_account_service = Column(
        Enum(
            AccountServiceType,
            values_callable=lambda x: [e.value for e in x],
            name="account_service_type"
        ),
        nullable=False
    )
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account_storage = relationship("AccountStorage", back_populates="product_account")
    category = relationship("Categories", back_populates="product_accounts")


class SoldAccounts(Base):
    """Хранит только проданные аккаунты, которые отображаются пользователю"""
    __tablename__ = "sold_accounts"
    __table_args__ = (
        Index('ix_sold_accounts_owner', 'owner_id'),
    )

    sold_account_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)
    type_account_service = Column(
        Enum(
            AccountServiceType,
            values_callable=lambda x: [e.value for e in x],
            name="account_service_type"
        ),
        nullable=False
    )

    sold_at = Column(DateTime(timezone=True), server_default=func.now())

    account_storage = relationship("AccountStorage", back_populates="sold_account")
    user = relationship("Users", back_populates="sold_account")
    translations = relationship("SoldAccountsTranslation", back_populates="sold_account", cascade="all, delete-orphan")

    def _get_field_with_translation(self,field: Callable[[Any], Any], lang: str, fallback: str = None)->str | None:
        """Вернёт по указанному языку, если такого не найдёт, то вернёт первый попавшийся"""
        for t in self.translations:
            if t.lang == lang:
                return field(t)
        if fallback:
            for t in self.translations:
                if t.lang == fallback:
                    return field(t)
        # вернём первый попавшийся
        if field(self.translations[0]):
            return field(self.translations[0])
        else:
            return None

    def get_name(self, lang: str, fallback: str = None)->str:
        """Вернёт по указанному языку, если такого не найдёт, то вернёт первый попавшийся"""
        return self._get_field_with_translation(lambda translations: translations.name, lang, fallback)

    def get_description(self, lang: str, fallback: str = None)->str:
        """Вернёт по указанному языку, если такого не найдёт, то вернёт первый попавшийся"""
        return self._get_field_with_translation(lambda translations: translations.description, lang, fallback)

    def to_localized_dict(self, language: str = None)->dict:
        new_dict = {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}
        new_dict.update({'name': self.get_name(language)})
        new_dict.update({'description': self.get_description(language)})
        return new_dict


class SoldAccountsTranslation(Base):
    """Всегда должна находиться как минимум одна запись для каждого sold_account_id"""
    __tablename__ = "sold_account_translations"
    __table_args__ = (
        UniqueConstraint("sold_account_id", "lang", name="uq_sold_accounts_lang"),
    )

    sold_account_translations_id = Column(Integer, primary_key=True, autoincrement=True)
    sold_account_id = Column(Integer, ForeignKey("sold_accounts.sold_account_id", ondelete="CASCADE"),nullable=False)
    lang = Column(String(8), nullable=False)  # 'ru', 'en'

    name = Column(Text, nullable=False) # берётся с Categories
    description = Column(Text, nullable=True) # берётся с Categories

    sold_account = relationship("SoldAccounts", back_populates="translations")


class DeletedAccounts(Base):
    """
    Аккаунты которые удалены либо пользователем, либо серверной частью по причине их не валидности
    """
    __tablename__ = "deleted_accounts"

    deleted_account_id = Column(Integer, primary_key=True, autoincrement=True)
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)
    type_account_service = Column(
        Enum(
            AccountServiceType,
            values_callable=lambda x: [e.value for e in x],
            name="account_service_type"
        ),
        nullable=False
    )
    category_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    create_at = Column(DateTime(timezone=True), server_default=func.now())

    account_storage = relationship("AccountStorage", back_populates="deleted_account")


class PurchaseRequestAccount(Base):
    __tablename__ = "purchase_request_accounts"

    purchase_request_accounts_id = Column(Integer, primary_key=True)
    purchase_request_id = Column(ForeignKey("purchase_requests.purchase_request_id"), nullable=False)
    account_storage_id = Column(ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)

    purchase_request = relationship("PurchaseRequests", back_populates="purchase_request_accounts")
    account_storage = relationship("AccountStorage", back_populates="purchase_request_accounts")
