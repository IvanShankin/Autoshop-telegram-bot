import shutil
from pathlib import Path
from typing import List

from sqlalchemy import select, delete

from src.config import get_config
from src.services.database.categories.models import ProductAccounts, \
    SoldAccounts, SoldAccountsTranslation, AccountStorage
from src.services.database.core.database import get_db
from src.services.filesystem.media_paths import create_path_account
from src.services.redis.filling import filling_all_keys_category, filling_sold_accounts_by_owner_id, \
    filling_product_account_by_account_id, filling_product_accounts_by_category_id, filling_sold_account_by_account_id


async def delete_product_account(account_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(ProductAccounts)
            .where(ProductAccounts.account_id == account_id)
        )
        account: ProductAccounts = result_db.scalar_one_or_none()
        if not account:
            raise ValueError(f"Аккаунта с id = {account_id} не найдено")

        await session_db.execute(delete(ProductAccounts).where(ProductAccounts.account_id == account_id))
        await session_db.commit()

        # обновляем redis
        await filling_product_accounts_by_category_id()
        await filling_product_account_by_account_id(account_id)
        await filling_all_keys_category(account.category_id)


async def delete_sold_account(account_id: int):
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(SoldAccounts)
            .where(SoldAccounts.sold_account_id == account_id)
        )
        account: SoldAccounts = result_db.scalar_one_or_none()
        if not account:
            raise ValueError(f"Аккаунта с id = {account_id} не найдено")

        await session_db.execute(delete(SoldAccounts).where(SoldAccounts.sold_account_id == account_id))
        await session_db.execute(delete(SoldAccountsTranslation).where(SoldAccountsTranslation.sold_account_id == account_id))
        await session_db.commit()

        # обновляем redis
        await filling_sold_accounts_by_owner_id(account.owner_id)
        await filling_sold_account_by_account_id(account.sold_account_id)


async def delete_product_accounts_by_category(category_id: int):
    """Удалит аккаунты в БД и на диске(если имеется)"""
    async with get_db() as session_db:
        product_ids_result = await session_db.execute(
            select(ProductAccounts.account_id)
            .where(ProductAccounts.category_id == category_id)
        )
        product_ids: List[int] = product_ids_result.scalars().all()

        result_db = await session_db.execute(
            delete(AccountStorage)
            .where(
                AccountStorage.account_storage_id.in_(
                    select(ProductAccounts.account_storage_id)
                    .where(ProductAccounts.category_id == category_id)
                )
            )
            .returning(AccountStorage)
        )
        delete_acc: List[AccountStorage] = result_db.scalars().all()
        await session_db.commit()

        for acc in delete_acc:

            if not acc.is_file: # если нет путь значит у всех остальных аккаунтов тоже нет
                continue

            folder = create_path_account(
                status=acc.status,
                type_account_service=acc.type_account_service,
                uuid=acc.storage_uuid,
                return_path_obj=True
            ).parent

            # удаляем каталог со всем содержимым
            shutil.rmtree(folder, ignore_errors=True)

        if delete_acc:
            await filling_all_keys_category(category_id=category_id)

            await filling_product_accounts_by_category_id()

            for acc_id in product_ids:
                await filling_product_account_by_account_id(acc_id)