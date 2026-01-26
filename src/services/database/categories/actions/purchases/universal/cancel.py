import shutil
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import select, update, delete

from src.services.database.categories.actions.purchases.general.cancel import return_files, \
    update_purchaseRequests_and_balance_holder
from src.services.database.categories.models import Purchases
from src.services.database.categories.models.product_universal import SoldUniversal, UniversalStorage, \
    UniversalStorageStatus, ProductUniversal
from src.services.database.categories.models.shemas.product_universal_schem import ProductUniversalFull
from src.services.database.core.database import get_db
from src.services.database.users.models import Users
from src.services.products.universals.actions import create_path_universal_storage
from src.services.redis.filling import filling_user, filling_all_keys_category
from src.services.redis.filling.filling_universal import filling_product_universal_by_category, \
    filling_sold_universal_by_owner_id, filling_sold_universal_by_universal_id, filling_universal_by_product_id
from src.utils.core_logger import get_logger


async def _filling_redis_universal(
    user: Users | None,
    user_id: int,
    category_id: int,
    sold_universal_ids: List[int],
    product_universal: List[ProductUniversalFull]
):
    """Для заполнения redis по всем необходимым ключам для универсальных товаров"""
    if user:
        await filling_user(user)

    await filling_sold_universal_by_owner_id(user_id)
    await filling_product_universal_by_category()

    for sid in sold_universal_ids:
        await filling_sold_universal_by_universal_id(sid)
    for prod in product_universal:
        await filling_universal_by_product_id(prod.product_universal_id)

    await filling_all_keys_category(category_id)


async def cancel_purchase_universal_one(
    user_id: int,
    category_id: int,
    paths_created_storage: List[Path],
    sold_universal_ids: List[int],
    storage_universal_ids: List[int],
    purchase_ids: List[int],
    total_amount: int,
    purchase_request_id: int,
    product_universal: ProductUniversalFull
):
    user = None
    logger = get_logger(__name__)

    for path in paths_created_storage:
        shutil.rmtree(path.parent, ignore_errors=True) # удаляем не только файл, а директорию где он лежит

    async with get_db() as session:
        async with session.begin():
            result_db = await session.execute(select(Users).where(Users.user_id == user_id))
            user: Users | None = result_db.scalars().one_or_none()
            if user is not None:
                new_balance = user.balance + total_amount
                await session.execute(
                    update(Users).where(Users.user_id == user_id).values(balance=new_balance)
                )

            # Удалим Purchases и SoldUniversal
            if purchase_ids:
                await session.execute(delete(Purchases).where(Purchases.purchase_id.in_(purchase_ids)))
            if sold_universal_ids:
                await session.execute(
                    delete(SoldUniversal)
                    .where(SoldUniversal.sold_universal_id.in_(sold_universal_ids))
                )
            if storage_universal_ids: # Их можно удалять т.к. они были скопированы
                await session.execute(
                    delete(UniversalStorage)
                    .where(UniversalStorage.universal_storage_id.in_(storage_universal_ids)
                ))

            # Обновляем PurchaseRequests и BalanceHolder
            await update_purchaseRequests_and_balance_holder(
                session=session,
                logger=logger,
                purchase_request_id=purchase_request_id
            )

    await _filling_redis_universal(user, user_id, category_id, sold_universal_ids, [product_universal])

    logger.info("cancel_purchase_universal_one finished for purchase %s", purchase_request_id)


async def cancel_purchase_universal_different(
    user_id: int,
    category_id: int,
    mapping: List[Tuple[str, str, str]],
    sold_universal_ids: List[int],
    purchase_ids: List[int],
    total_amount: int,
    purchase_request_id: int,
    product_universal: List[ProductUniversalFull],
):
    """
    получает mapping и пытается вернуть файлы и БД в исходное состояние

    :param mapping: список кортежей (orig_path, temp_path, final_path)
     - orig_path: изначальный путь (старое место)
     - temp_path: временный путь куда мы переместили файл до коммита
     - final_path: финальный путь (куда будет переименован после commit)
    :param sold_universal_ids: список уже созданных sold_universal (если есть) — удалим их и вернём product-строки
    :param purchase_ids: список purchases_universal — удалим Purchases
    """
    user = None
    logger = get_logger(__name__)

    await return_files(mapping, logger)

    # Удалить sold_universal & purchases и вернуть UniversalStorage.status = 'for_sale'
    async with get_db() as session:
        async with session.begin():
            # возвращаем баланс
            result_db = await session.execute(select(Users).where(Users.user_id == user_id))
            user: Users | None = result_db.scalars().one_or_none()
            if user is not None:
                new_balance = user.balance + total_amount
                await session.execute(
                    update(Users).where(Users.user_id == user_id).values(balance=new_balance)
                )

            # Удалим Purchases и SoldUniversal
            if purchase_ids:
                await session.execute(delete(Purchases).where(Purchases.purchase_id.in_(purchase_ids)))
            if sold_universal_ids:
                await session.execute(
                    delete(SoldUniversal)
                    .where(SoldUniversal.sold_universal_id.in_(sold_universal_ids))
                )

            try:
                universal_storages_ids = [prod.universal_storage_id for prod in product_universal]

                result = await session.execute(
                    select(UniversalStorage)
                    .where(UniversalStorage.universal_storage_id.in_(universal_storages_ids))
                    .with_for_update()
                )
                storages: List[UniversalStorage] = result.scalars().all()

                for s in storages:
                    new_path = create_path_universal_storage(status=s.status, uuid=s.storage_uuid)
                    await session.execute(
                        update(UniversalStorage)
                        .where(UniversalStorage.universal_storage_id == s.universal_storage_id)
                        .values(
                            status=UniversalStorageStatus.FOR_SALE,
                            file_path=new_path
                        )
                    )

                existing = await session.execute(
                    select(ProductUniversal.universal_storage_id)
                    .where(ProductUniversal.universal_storage_id.in_(universal_storages_ids))
                )
                existing_ids = set(existing.scalars().all())

                for product in product_universal:
                    uid = product.universal_storage_id
                    if uid not in existing_ids:
                        session.add(ProductUniversal(
                            universal_storage_id=uid,
                            category_id=product.category_id,
                        ))

            except Exception:
                logger.exception("Failed to restore universal storage status")

            # Обновляем PurchaseRequests и BalanceHolder
            await update_purchaseRequests_and_balance_holder(
                session=session,
                logger=logger,
                purchase_request_id=purchase_request_id
            )

    await _filling_redis_universal(user, user_id, category_id, sold_universal_ids, product_universal)

    logger.info("cancel_purchase_universal_different finished for purchase %s", purchase_request_id)
