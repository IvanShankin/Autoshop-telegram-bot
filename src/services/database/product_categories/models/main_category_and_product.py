from typing import Callable, Any
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text, text, UniqueConstraint, inspect, Enum
from sqlalchemy.orm import relationship

from src.services.database.core.database import Base



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
    price = Column(Integer, nullable=True, server_default=text("0"))
    cost_price = Column(Integer, nullable=True, server_default=text("0"))

    products = relationship("Products", back_populates="category")
    next_categories = relationship("Categories",back_populates="parent",foreign_keys=[parent_id])
    ui_image = relationship("UiImages",back_populates="category")
    parent = relationship("Categories",back_populates="next_categories",remote_side=lambda: [Categories.category_id])
    translations = relationship("CategoryTranslation", back_populates="category", cascade="all, delete-orphan")

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


class Products(Base):
    """Это продукт к нему могут быть прикреплены бесконечно количество конкретных товаров """
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.category_id"))

    product_type = Column(Enum(
        "account",
        "universal",
        "file",
        name="product_type"
    ), nullable=False)

    category = relationship("Categories", back_populates="products")
    product_accounts = relationship("ProductAccounts", back_populates="product")
    product_universal = relationship("ProductUniversal", back_populates="product")

