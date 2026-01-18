import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from tests.helpers.func_fabrics.other_fabric import create_ui_image_factory
from src.services.database.categories.models import Categories, CategoryTranslation, CategoryFull
from src.services.database.categories.models.main_category_and_product import ProductType
from src.services.database.categories.models.product_account import AccountServiceType
from src.services.database.core.database import get_db
from src.services.redis.filling import filling_all_keys_category


async def create_translate_category_factory(
        category_id: int,
        filling_redis: bool = True,
        language: str = "ru",
        name: str = "name",
        description: str = "description"
) -> CategoryFull:
    from src.services.database.categories.actions import get_quantity_products_in_category

    async with get_db() as session_db:
        new_translate = CategoryTranslation(
            category_id=category_id,
            lang=language,
            name=name,
            description=description
        )
        session_db.add(new_translate)
        await session_db.commit()

        result = await session_db.execute(
            select(Categories)
            .options(selectinload(Categories.translations))
            .where(Categories.category_id == category_id)
        )
        category = result.scalar_one()

        full_category = CategoryFull.from_orm_with_translation(
            category=category,
            quantity_product=await get_quantity_products_in_category(category_id),
            lang=language
        )

    if filling_redis:
        await filling_all_keys_category()

    return full_category


async def create_category_factory(
        filling_redis: bool = True,
        parent_id: int = None,
        ui_image_key: str = None,
        index: int = None,
        show: bool = True,
        is_main: bool = True,
        is_product_storage: bool = False,
        product_type: str = ProductType.ACCOUNT,
        type_account_service: AccountServiceType = AccountServiceType.TELEGRAM,
        price: int = 150,
        cost_price: int = 100,
        language: str = "ru",
        name: str = "name",
        description: str = "description"
) -> CategoryFull:
    from src.services.database.categories.actions import get_quantity_products_in_category

    async with get_db() as session_db:
        if parent_id is not None:
            is_main = False
        if ui_image_key is None:
            ui_image, path = await create_ui_image_factory(key=str(uuid.uuid4()))
            ui_image_key = ui_image.key
        if index is None:
            result_db = await session_db.execute(
                select(Categories)
                .where(Categories.parent_id == parent_id)
                .order_by(Categories.index.asc())
            )
            all_categories: list[Categories] = result_db.scalars().all()  # тут уже отсортированный по index
            index = max((category.index for category in all_categories), default=-1) + 1

        new_category = Categories(
            parent_id = parent_id,
            ui_image_key = ui_image_key,
            index = index,
            show = show,
            is_main = is_main,
            is_product_storage = is_product_storage,
            product_type=product_type,
            type_account_service=type_account_service,
            price = price,
            cost_price = cost_price
        )
        session_db.add(new_category)
        await session_db.commit()
        await session_db.refresh(new_category)

        new_translate = CategoryTranslation(
            category_id=new_category.category_id,
            lang=language,
            name=name,
            description=description
        )
        session_db.add(new_translate)
        await session_db.commit()

        # Перечитываем объект с подгруженными translations
        result = await session_db.execute(
            select(Categories)
            .options(selectinload(Categories.translations))
            .where(Categories.category_id == new_category.category_id)
        )
        new_category = result.scalar_one()

        full_category = CategoryFull.from_orm_with_translation(
            category = new_category,
            quantity_product=await get_quantity_products_in_category(new_category.category_id),
            lang = language,
        )
        if filling_redis:
            await filling_all_keys_category()

    return full_category

