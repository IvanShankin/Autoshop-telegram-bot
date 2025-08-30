from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text, Index, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database.database import Base


class TypeAccountServices(Base):
    """
    Эту таблицу в боте нельзя менять. Тут по умолчанию должно быть поле с "телеграм" и "другой".
    В дальнейших обновлениях будут расширятся сервисы с которыми работаем
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
    Их задаёт пользователь. Один тип сервиса (TypeAccountServices) - один привязанный к нему сервис (AccountServices)
    """
    __tablename__ = "account_services"

    account_service_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False, unique=True) # помечать будем в боте

    account_categories = relationship("AccountCategories", back_populates="account_service")
    type_account_service = relationship("TypeAccountServices", back_populates="account_service")


class AccountCategories(Base):
    """
    Категории у аккаунтов, к каждой категории может быть подкатегория (подкатегория это тоже запись в БД)
    Если есть флаг is_main, то у данной категории нет родителя.
    Если есть флаг is_accounts_storage, то данная категория хранит аккаунты и задействована для продажи
    """
    __tablename__ = "account_categories"

    account_category_id = Column(Integer, primary_key=True, autoincrement=True)
    account_service_id = Column(Integer, ForeignKey("account_services.account_service_id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("account_categories.account_category_id"), nullable=True)
    name = Column(String(300), nullable=False) # будет отображать на кнопке и в самом товаре
    description = Column(Text, nullable=False)
    is_main = Column(Boolean, nullable=False, server_default=text('false'))
    is_accounts_storage = Column(Boolean, nullable=False, server_default=text('false')) # если это хранилище аккаунтов

    # только для тех категорий которые хранят аккаунты (is_accounts_storage == True)
    price_one_account = Column(Integer, nullable=True) # цена продажи
    cost_price_one_account = Column(Integer, nullable=True) # себестоимость

    account_service = relationship("AccountServices", back_populates="account_categories")
    next_account_categories = relationship("AccountCategories",back_populates="parent",foreign_keys=[parent_id])
    parent = relationship("AccountCategories",back_populates="next_account_categories",remote_side=lambda: [AccountCategories.account_category_id])
    product_accounts = relationship("ProductAccounts", back_populates="account_category")

class ProductAccounts(Base):
    __tablename__ = "product_accounts"
    __table_args__ = (
        Index('ix_accounts_type_service', 'type_account_service_id'),
        Index('ix_accounts_category', 'account_category_id'),
    )

    account_id = Column(Integer, primary_key=True, autoincrement=True)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False)
    account_category_id = Column(Integer, ForeignKey("account_categories.account_category_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Специфичные поля (могут быть NULL)
    hash_login = Column(Text, nullable=True)
    hash_password = Column(Text, nullable=True)

    type_account_service = relationship("TypeAccountServices", back_populates="product_accounts")
    account_category = relationship("AccountCategories", back_populates="product_accounts")

# хранит проданные аккаунты
class SoldAccounts(Base):
    __tablename__ = "sold_accounts"
    __table_args__ = (
        Index('ix_sold_accounts_owner', 'owner_id'),
        Index('ix_sold_accounts_type', 'type_account_service_id', 'is_valid', 'is_deleted'),
    )

    sold_account_id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    type_account_service_id = Column(Integer, ForeignKey("type_account_services.type_account_service_id"), nullable=False)

    category_name = Column(String(300), nullable=False) # берётся с AccountCategories
    service_name = Column(String(300), nullable=False) # берётся с AccountServices
    type_name = Column(String(100), nullable=False)

    is_valid = Column(Boolean, nullable=False, server_default=text('true'))
    is_deleted = Column(Boolean, nullable=False, server_default=text('false'))

    # Специфичные поля (могут быть NULL)
    hash_login = Column(Text, nullable=True)
    hash_password = Column(Text, nullable=True)

    user = relationship("Users", back_populates="sold_account")
    type_account_service = relationship("TypeAccountServices", back_populates="sold_accounts")
    purchase = relationship("PurchasesAccounts", back_populates="sold_account", uselist=False)

# если запись есть, то это покупка совершённая
class PurchasesAccounts(Base):
    __tablename__ = "purchases_accounts"
    __table_args__ = (
        Index('ix_purchase_date', 'user_id', 'purchase_date'),
    )

    purchase_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
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


