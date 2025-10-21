from typing import Callable, Any

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Index, text, UniqueConstraint, \
    inspect, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

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
    Если установлен флаг is_main, то у данной категории нет родителя.
    Если установлен флаг is_accounts_storage, то данная категория хранит аккаунты и задействована для продажи
    """
    __tablename__ = "account_categories"

    account_category_id = Column(Integer, primary_key=True, autoincrement=True)
    account_service_id = Column(Integer, ForeignKey("account_services.account_service_id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("account_categories.account_category_id"), nullable=True)
    index = Column(Integer)
    show = Column(Boolean, nullable=False, server_default=text('true'))
    is_main = Column(Boolean, nullable=False, server_default=text('false'))
    is_accounts_storage = Column(Boolean, nullable=False, server_default=text('false')) # если это хранилище аккаунтов

    # только для тех категорий которые хранят аккаунты (is_accounts_storage == True)
    price_one_account = Column(Integer, nullable=True) # цена продажи
    cost_price_one_account = Column(Integer, nullable=True) # себестоимость

    account_service = relationship("AccountServices", back_populates="account_categories")
    next_account_categories = relationship("AccountCategories",back_populates="parent",foreign_keys=[parent_id])
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

class ProductAccounts(Base):
    __tablename__ = "product_accounts"
    __table_args__ = (
        Index('ix_accounts_type_service', 'type_account_service_id'),
        Index('ix_accounts_category', 'account_category_id'),
    )

    account_id = Column(Integer, primary_key=True, autoincrement=True)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False)
    account_category_id = Column(Integer, ForeignKey("account_categories.account_category_id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Специфичные поля (могут быть NULL)
    hash_login = Column(Text, nullable=True)
    hash_password = Column(Text, nullable=True)

    type_account_service = relationship("TypeAccountServices", back_populates="product_accounts")
    account_category = relationship("AccountCategories", back_populates="product_accounts")

class SoldAccounts(Base):
    __tablename__ = "sold_accounts"
    __table_args__ = (
        Index('ix_sold_accounts_owner', 'owner_id'),
        Index('ix_sold_accounts_type', 'type_account_service_id', 'is_valid', 'is_deleted'),
    )

    sold_account_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=True)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False)

    is_valid = Column(Boolean, nullable=False, server_default=text('true'))
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))

    # Специфичные поля (могут быть NULL)
    hash_login = Column(Text, nullable=True)
    hash_password = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="sold_account")
    type_account_service = relationship("TypeAccountServices", back_populates="sold_accounts")
    purchase = relationship("PurchasesAccounts", back_populates="sold_account", uselist=False)
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
    description = Column(Text, nullable=False) # берётся с AccountCategories

    sold_account = relationship("SoldAccounts", back_populates="translations")

class PurchasesAccounts(Base):
    """если запись есть, то это покупка совершённая"""
    __tablename__ = "purchases_accounts"
    __table_args__ = (
        Index('ix_purchase_date', 'user_id', 'purchase_date'),
    )

    purchase_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    sold_account_id = Column(Integer, ForeignKey("sold_accounts.sold_account_id"), nullable=False)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.promo_code_id"), nullable=True)

    original_price = Column(Integer, nullable=False)  # Цена на момент покупки (без учёта промокода)
    purchase_price = Column(Integer, nullable=False)  # Цена на момент покупки (с учётом промокода)
    cost_price = Column(Integer, nullable=False)  # Себестоимость на момент покупки

    net_profit = Column(Integer, nullable=False)  # Чистая прибыль
    purchase_date = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="purchases")
    sold_account = relationship("SoldAccounts", back_populates="purchase")  # Связь с SoldAccounts
    promo_code = relationship("PromoCodes", back_populates="purchases_accounts")

class DeletedAccounts(Base):
    """
    Логирование аккаунтов которые удалены самим ботом по причине их не валидности.
    Аккаунты удалённые пользователем сюда не попадают!
    """
    __tablename__ = "deleted_accounts"

    deleted_account_id = Column(Integer, primary_key=True, autoincrement=True)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False)
    category_name = Column(Text, nullable=False)
    description = Column(Text, nullable=False)

    create_at = Column(DateTime(timezone=True), server_default=func.now())

