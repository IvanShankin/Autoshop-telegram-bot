from sqlalchemy import select, delete

from src.services.database.categories.models import ProductUniversal
from src.services.database.categories.models.product_universal import SoldUniversal
from src.services.database.core import get_db
from src.services.redis.filling import filling_all_keys_category
from src.services.redis.filling.filling_universal import filling_product_universal_by_category, \
    filling_universal_by_product_id, filling_sold_universal_by_owner_id, filling_sold_universal_by_universal_id


async def delete_prod_universal(
    product_universal_id: int
):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(ProductUniversal)
            .where(ProductUniversal.product_universal_id == product_universal_id)
        )
        product: ProductUniversal = result_db.scalar_one_or_none()
        if not product:
            raise ValueError(f"Продукт с id = {product_universal_id} не найдено")

        await session_db.execute(
            delete(ProductUniversal)
            .where(ProductUniversal.product_universal_id == product_universal_id)
        )
        await session_db.commit()

        # обновляем redis
        await filling_product_universal_by_category()
        await filling_universal_by_product_id(product.product_universal_id)
        await filling_all_keys_category(product.category_id)


async def delete_sold_universal(
    sold_universal_id: int
):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_universal_id)
        )
        sold: SoldUniversal = result_db.scalar_one_or_none()
        if not sold:
            raise ValueError(f"Продукт с id = {sold_universal_id} не найдено")

        await session_db.execute(
            delete(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_universal_id)
        )
        await session_db.commit()

        # обновляем redis
        await filling_sold_universal_by_owner_id(sold.owner_id)
        await filling_sold_universal_by_universal_id(sold_universal_id)
