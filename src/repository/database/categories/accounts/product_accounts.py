from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from src.database.models.categories import (
    ProductAccounts,
    AccountStorage,
    StorageStatus,
)
from src.repository.database.base import DatabaseBase


class ProductAccountsRepository(DatabaseBase):

    async def get_by_account_id(
        self,
        account_id: int,
        *,
        with_storage: bool = False,
    ) -> Optional[ProductAccounts]:
        stmt = select(ProductAccounts).where(ProductAccounts.account_id == account_id)
        if with_storage:
            stmt = stmt.options(selectinload(ProductAccounts.account_storage))

        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_category_id(
        self,
        category_id: int,
        *,
        only_for_sale: bool = True,
        with_storage: bool = False,
    ) -> List[ProductAccounts]:
        stmt = select(ProductAccounts).where(ProductAccounts.category_id == category_id)

        if only_for_sale:
            stmt = stmt.join(ProductAccounts.account_storage).where(
                AccountStorage.status == StorageStatus.FOR_SALE
            )

        if with_storage:
            stmt = stmt.options(selectinload(ProductAccounts.account_storage))

        result = await self.session_db.execute(stmt)
        return list(result.scalars().all())

    async def get_account_ids_by_category_id(self, category_id: int) -> List[int]:
        result = await self.session_db.execute(
            select(ProductAccounts.account_id).where(ProductAccounts.category_id == category_id)
        )
        return list(result.scalars().all())

    async def get_storage_ids_by_category_id(self, category_id: int) -> List[int]:
        result = await self.session_db.execute(
            select(ProductAccounts.account_storage_id).where(ProductAccounts.category_id == category_id)
        )
        return list(result.scalars().all())

    async def create_product(self, **values) -> ProductAccounts:
        return await super().create(ProductAccounts, **values)

    async def delete_by_account_id(self, account_id: int) -> None:
        await self.session_db.execute(
            delete(ProductAccounts).where(ProductAccounts.account_id == account_id)
        )

    async def delete_by_category_id(self, category_id: int) -> None:
        await self.session_db.execute(
            delete(ProductAccounts).where(ProductAccounts.category_id == category_id)
        )

    async def exists_by_account_id(self, account_id: int) -> bool:
        result = await self.session_db.execute(
            select(ProductAccounts.account_id).where(ProductAccounts.account_id == account_id)
        )
        return result.scalar_one_or_none() is not None