from typing import Callable, Any

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Index, text, UniqueConstraint, \
    inspect, BigInteger, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.services.database.core.database import Base


class TypeAccountServices(Base):
    """
    Эту таблицу в боте нельзя менять, она задаётся только через код.
    Администрация будет выбирать из этого списка при создании нового AccountServices
    Тут по умолчанию должно быть поле с "телеграм" и "другой".
    В дальнейших обновлениях будут расширятся сервисы с которыми работаем.
    Это сделано потому что для разных аккаунтов необходимо использовать разный подход для входа в него
    """
    __tablename__ = "type_account_services"

    type_account_service_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)

    account_service = relationship("AccountServices", back_populates="type_account_service")
    product_accounts = relationship("ProductAccounts", back_populates="type_account_service")
    sold_accounts = relationship("SoldAccounts", back_populates="type_account_service")

class AccountServices(Base):
    """
    Хранит сервисы у продаваемых аккаунтов, такие как: telegram, vk, instagram ...
    Их задаёт администрация. Один тип сервиса (TypeAccountServices) - один привязанный к нему сервис (AccountServices)
    Сервисы локализировать не будут, т.к. они имеют свою уникальное название.
    """
    __tablename__ = "account_services"

    account_service_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    index = Column(Integer)
    show = Column(Boolean, nullable=False, server_default=text('true'))
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False, unique=True) # помечать будем в боте

    account_categories = relationship("AccountCategories", back_populates="account_service")
    type_account_service = relationship("TypeAccountServices", back_populates="account_service")


class AccountCategories(Base):
    """
    Категории у аккаунтов, к каждой категории может быть подкатегория (подкатегория это тоже запись в БД)

    Если установлен флаг show, то данная категория будет показываться пользователю (админу всегда показывается).

    Если у категории нет аккаунтов, то она не отображается пользователю.

    Если установлен флаг is_main, то у данной категории нет родителя.

    Если установлен флаг is_accounts_storage, то данная категория хранит аккаунты и задействована для продажи
    """
    __tablename__ = "account_categories"

    account_category_id = Column(Integer, primary_key=True, autoincrement=True)
    account_service_id = Column(Integer, ForeignKey("account_services.account_service_id"), nullable=False, index=True)
    ui_image_key = Column(String, ForeignKey("ui_images.key"), nullable=False)
    parent_id = Column(Integer, ForeignKey("account_categories.account_category_id"), nullable=True)
    index = Column(Integer)
    show = Column(Boolean, nullable=False, server_default=text('true'))
    # количество кнопок для перехода в другую категорию на одну строку от 1 до 8
    number_buttons_in_row = Column(Integer, nullable=False, server_default=text('1'))
    is_main = Column(Boolean, nullable=False, server_default=text('false'))
    is_accounts_storage = Column(Boolean, nullable=False, server_default=text('false')) # если это хранилище аккаунтов

    # только для тех категорий которые хранят аккаунты (is_accounts_storage == True)
    price_one_account = Column(Integer, nullable=True, server_default=text("0")) # цена продажи
    cost_price_one_account = Column(Integer, nullable=True, server_default=text("0")) # себестоимость

    account_service = relationship("AccountServices", back_populates="account_categories")
    next_account_categories = relationship("AccountCategories",back_populates="parent",foreign_keys=[parent_id])
    ui_image = relationship("UiImages",back_populates="account_category")
    parent = relationship("AccountCategories",back_populates="next_account_categories",remote_side=lambda: [AccountCategories.account_category_id])
    product_accounts = relationship("ProductAccounts", back_populates="account_category")
    translations = relationship("AccountCategoryTranslation", back_populates="account_category", cascade="all, delete-orphan")

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

    def get_name(self, lang: str, fallback: str | None = None)->str:
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


class AccountCategoryTranslation(Base):
    """Всегда должна находиться как минимум одна запись для каждого account_category_id"""
    __tablename__ = "account_category_translations"
    __table_args__ = (
        UniqueConstraint("account_category_id", "lang", name="uq_category_lang"),
    )

    account_category_translations_id = Column(Integer, primary_key=True, autoincrement=True)
    account_category_id = Column(Integer, ForeignKey("account_categories.account_category_id", ondelete="CASCADE"),nullable=False, index=True)
    lang = Column(String(8), nullable=False)  # 'ru', 'en'
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)

    account_category = relationship("AccountCategories", back_populates="translations")


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
    encrypted_key_nonce = Column(Text, nullable=False) # nonce, использованный при wrap (Nonce (IV) для AES-GCM (base64))
    key_version = Column(Integer, nullable=False, server_default=text("1")) # Номер мастер-ключа (для ротации)
    encryption_algo = Column(String(32), nullable=False, server_default=text("'AES-GCM-256'")) # Алгоритм шифрования

    # === Основные поля ===
    phone_number = Column(String(100), nullable=False) # Пример: +79161234567
    login_encrypted = Column(Text, nullable=True)
    password_encrypted = Column(Text, nullable=True)

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
    purchase = relationship("PurchasesAccounts", back_populates="account_storage", uselist=False)
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
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False, index=True)
    account_category_id = Column(Integer, ForeignKey("account_categories.account_category_id"), nullable=False, index=True)
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    type_account_service = relationship("TypeAccountServices", back_populates="product_accounts")
    account_storage = relationship("AccountStorage", back_populates="product_account")
    account_category = relationship("AccountCategories", back_populates="product_accounts")

class SoldAccounts(Base):
    """Хранит только проданные аккаунты, которые отображаются пользователю"""
    __tablename__ = "sold_accounts"
    __table_args__ = (
        Index('ix_sold_accounts_owner', 'owner_id'),
        Index('ix_sold_accounts_type', 'type_account_service_id'),
    )

    sold_account_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False)

    sold_at = Column(DateTime(timezone=True), server_default=func.now())

    account_storage = relationship("AccountStorage", back_populates="sold_account")
    user = relationship("Users", back_populates="sold_account")
    type_account_service = relationship("TypeAccountServices", back_populates="sold_accounts")
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

    name = Column(Text, nullable=False) # берётся с AccountCategories
    description = Column(Text, nullable=True) # берётся с AccountCategories

    sold_account = relationship("SoldAccounts", back_populates="translations")

class PurchasesAccounts(Base):
    """если запись есть, то это покупка совершённая"""
    __tablename__ = "purchases_accounts"
    __table_args__ = (
        Index('ix_purchase_date', 'user_id', 'purchase_date'),
    )

    purchase_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)

    original_price = Column(Integer, nullable=False)  # Цена на момент покупки (без учёта промокода)
    purchase_price = Column(Integer, nullable=False)  # Цена на момент покупки (с учётом промокода)
    cost_price = Column(Integer, nullable=False)  # Себестоимость на момент покупки

    net_profit = Column(Integer, nullable=False)  # Чистая прибыль
    purchase_date = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="purchases")
    account_storage = relationship("AccountStorage", back_populates="purchase")

class DeletedAccounts(Base):
    """
    Аккаунты которые удалены либо пользователем, либо серверной частью по причине их не валидности
    """
    __tablename__ = "deleted_accounts"

    deleted_account_id = Column(Integer, primary_key=True, autoincrement=True)
    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False)
    category_name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    create_at = Column(DateTime(timezone=True), server_default=func.now())

    account_storage = relationship("AccountStorage", back_populates="deleted_account")


class PurchaseRequests(Base):
    __tablename__ = "purchase_requests"

    purchase_request_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.promo_code_id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Integer, nullable=False)
    status = Column(Enum('processing', 'completed', 'failed', name='status_request'), server_default='processing')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    purchase_request_accounts = relationship("PurchaseRequestAccount", back_populates="purchase_request")
    promo_code = relationship("PromoCodes", back_populates="purchase_requests")
    user = relationship("Users", back_populates="purchase_requests")
    balance_holder = relationship("BalanceHolder", back_populates="purchase_requests")


class PurchaseRequestAccount(Base):
    __tablename__ = "purchase_request_accounts"

    purchase_request_accounts_id = Column(Integer, primary_key=True)
    purchase_request_id = Column(ForeignKey("purchase_requests.purchase_request_id"), nullable=False)
    account_storage_id = Column(ForeignKey("account_storage.account_storage_id", ondelete="CASCADE"), nullable=False)

    purchase_request = relationship("PurchaseRequests", back_populates="purchase_request_accounts")
    account_storage = relationship("AccountStorage", back_populates="purchase_request_accounts")
