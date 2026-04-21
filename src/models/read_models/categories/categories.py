from typing import Optional

from pydantic import ConfigDict

from src.database.models.categories import ProductType, AccountServiceType, UniversalMediaType, Categories
from src.models.base import ORMDTO


class CategoriesDTO(ORMDTO):
    category_id: int
    ui_image_key: str
    parent_id: int | None
    index: int | None
    show: bool
    number_buttons_in_row: int
    is_main: bool
    is_product_storage: bool
    allow_multiple_purchase: bool
    product_type: ProductType | None
    type_account_service: AccountServiceType | None
    media_type: UniversalMediaType | None
    reuse_product: bool | None
    price: int | None
    cost_price: int | None


class CategoryTranslationDTO(ORMDTO):
    category_translations_id: int
    category_id: int
    language: str
    name: str
    description: str | None


class CategoryFull(ORMDTO):
    category_id: int
    ui_image_key: str
    parent_id: Optional[int]

    language: str
    name: str
    description: Optional[str]

    index: int
    show: bool
    number_buttons_in_row: int

    is_main: bool
    is_product_storage: bool
    allow_multiple_purchase: bool # разрешена продажа одного товара много раз

    # только для тех кто хранит товары,
    product_type: ProductType | None
    type_account_service: AccountServiceType | None
    media_type: UniversalMediaType | None

    # только для категорий которые хранят универсальные товары
    reuse_product: bool | None

    price: int | None
    cost_price: int | None

    # Число товаров на продаже которое хранит в себе. Есть только у категорий хранящие продукты
    quantity_product: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_translation(
            cls,
            category: Categories,
            quantity_product:int,
            language: str,
            fallback: str | None = None,
            name: str = None,
            description: str = None,
        ):
        """orm модель превратит в CategoryFull"""
        return cls(
            category_id=category.category_id,
            ui_image_key=category.ui_image_key,
            parent_id=category.parent_id,
            index=category.index,
            show=category.show,
            number_buttons_in_row=category.number_buttons_in_row,
            is_main=category.is_main,

            language=language,
            name=name if name else category.get_name(language, fallback),
            description=description if description else category.get_description(language, fallback),

            is_product_storage=category.is_product_storage,
            allow_multiple_purchase=category.allow_multiple_purchase,

            product_type=category.product_type,
            type_account_service=category.type_account_service,
            media_type=category.media_type,
            reuse_product=category.reuse_product,
            price=category.price,
            cost_price=category.cost_price,

            quantity_product=quantity_product,
        )