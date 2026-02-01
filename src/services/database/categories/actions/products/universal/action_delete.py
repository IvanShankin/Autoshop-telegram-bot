import shutil
from typing import List

from sqlalchemy import select, delete

from src.services.database.categories.models import ProductUniversal
from src.services.database.categories.models.product_universal import SoldUniversal, UniversalStorage
from src.services.database.core import get_db
from src.services.filesystem.media_paths import create_path_universal_storage
from src.services.redis.filling import filling_all_keys_category, filling_product_accounts_by_category_id
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


async def delete_product_universal_by_category(category_id: int):
    """Удалит аккаунты в БД и на диске(если имеется)"""
    async with get_db() as session_db:
        products_result = await session_db.execute(
            select(ProductUniversal)
            .where(ProductUniversal.category_id == category_id)
        )
        products: List[ProductUniversal] = products_result.scalars().all()

        result_db = await session_db.execute(
            delete(UniversalStorage)
            .where(
                UniversalStorage.universal_storage_id.in_(
                    [prod.universal_storage_id for prod in products]
                )
            )
            .returning(UniversalStorage)
        )
        delete_storages: List[UniversalStorage] = result_db.scalars().all()
        await session_db.commit()

    for storage in delete_storages:

        if not storage.file_path: # если нет путь значит у всех остальных аккаунтов тоже нет
            continue

        folder = create_path_universal_storage(
            status=storage.status,
            uuid=storage.storage_uuid,
            return_path_obj=True
        )

        # удаляем каталог со всем содержимым
        shutil.rmtree(folder.parent, ignore_errors=True)

    if delete_storages:
        await filling_all_keys_category(category_id=category_id)

        await filling_product_universal_by_category()

        for prod in products:
            await filling_universal_by_product_id(prod.product_universal_id)