import enum
from typing import Callable, Any
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text, text, UniqueConstraint, inspect, Enum, \
    BigInteger, Index, DateTime, func
from sqlalchemy.orm import relationship

from src.services.database.core.database import Base
from src.services.database.categories.models.product_account import AccountServiceType


class ProductType(enum.Enum):
    ACCOUNT = "account"
    UNIVERSAL = "universal"


class Categories(Base):
    """
    Категории у аккаунтов, к каждой категории может быть подкатегория (подкатегория это тоже запись в БД)

    Если установлен флаг show, то данная категория будет показываться пользователю (админу всегда показывается).

    Если у категории нет аккаунтов, то она не отображается пользователю.

    Если установлен флаг is_main, то у данной категории нет родителя.

    Если установлен флаг is_product_storage, то данная категория хранит аккаунты и задействована для продажи
    """
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, autoincrement=True)
    ui_image_key = Column(String, ForeignKey("ui_images.key"), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.category_id"), nullable=True)
    index = Column(Integer)
    show = Column(Boolean, nullable=False, server_default=text('true'))
    # количество кнопок для перехода в другую категорию на одну строку от 1 до 8
    number_buttons_in_row = Column(Integer, nullable=False, server_default=text('1'))

    is_main = Column(Boolean, nullable=False, server_default=text('false'))
    is_product_storage = Column(Boolean, nullable=False, server_default=text('false')) # если это хранилище товаров

    # есть только когда is_product_storage == True
    allow_multiple_purchase = Column(Boolean, nullable=False, server_default=text("true"))
    product_type = Column(
        Enum(
            ProductType,
            values_callable=lambda x: [e.value for e in x],
            name="product_type"
        ),
        nullable=True
    )
    type_account_service = Column(
        Enum(
            AccountServiceType,
            values_callable=lambda x: [e.value for e in x],
            name="account_service_type"
        ),
        nullable=True
    ) # только для категорий хранящие аккаунты

    # Можно использовать один товар для продажи много раз. Будет браться первый стоящий на продажу
    reuse_product = Column(Boolean, nullable=True, server_default=text("false")) # только для категорий хранящие универсальные товары

    price = Column(Integer, nullable=True, server_default=text("0"))
    cost_price = Column(Integer, nullable=True, server_default=text("0"))

    next_categories = relationship("Categories",back_populates="parent",foreign_keys=[parent_id])
    ui_image = relationship("UiImages",back_populates="category")
    parent = relationship("Categories",back_populates="next_categories",remote_side=lambda: [Categories.category_id])
    translations = relationship("CategoryTranslation", back_populates="category", cascade="all, delete-orphan")

    product_universals = relationship("ProductUniversal", back_populates="category",)
    product_accounts = relationship("ProductAccounts", back_populates="category",)

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


class CategoryTranslation(Base):
    """Всегда должна находиться как минимум одна запись для каждого category_id"""
    __tablename__ = "category_translations"
    __table_args__ = (
        UniqueConstraint("category_id", "lang", name="uq_category_lang"),
    )

    category_translations_id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.category_id", ondelete="CASCADE"),nullable=False, index=True)
    lang = Column(String(8), nullable=False)  # 'ru', 'en'
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)

    category = relationship("Categories", back_populates="translations")


class Purchases(Base):
    """если запись есть, то это покупка совершённая"""
    __tablename__ = "purchases"
    __table_args__ = (
        Index('ix_purchase_date', 'user_id', 'purchase_date'),
    )

    purchase_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)

    product_type = Column(
        Enum(
            ProductType,
            values_callable=lambda x: [e.value for e in x],
            name="product_type"
        ),
        nullable=True
    )

    account_storage_id = Column(Integer, ForeignKey("account_storage.account_storage_id"), nullable=True)
    universal_storage_id = Column(Integer, ForeignKey("universal_storage.universal_storage_id"), nullable=True)

    original_price = Column(Integer, nullable=False)  # Цена на момент покупки (без учёта промокода)
    purchase_price = Column(Integer, nullable=False)  # Цена на момент покупки (с учётом промокода)
    cost_price = Column(Integer, nullable=False)  # Себестоимость на момент покупки
    net_profit = Column(Integer, nullable=False)  # Чистая прибыль

    purchase_date = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Users", back_populates="purchases")
    account_storage = relationship("AccountStorage", back_populates="purchase")