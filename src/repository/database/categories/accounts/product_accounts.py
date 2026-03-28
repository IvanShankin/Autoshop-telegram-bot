from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from src.database.models.categories import (
    ProductAccounts,
    AccountStorage,
    StorageStatus,
    AccountServiceType,
)
from src.models.read_models import ProductAccountSmall
from src.models.read_models.categories.accounts import ProductAccountFull
from src.repository.database.base import DatabaseBase


class ProductAccountsRepository(DatabaseBase):

    async def get_full_by_account_id(
            self,
            account_id: int,
    ) -> Optional[ProductAccountFull]:
        stmt = (
            select(ProductAccounts)
            .options(selectinload(ProductAccounts.account_storage))
            .where(ProductAccounts.account_id == account_id)
        )

        result = await self.session_db.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            return None

        return ProductAccountFull.from_orm_model(
            product_account=product,
            storage_account=product.account_storage,
        )

    async def get_full_by_category_id(
        self,
        category_id: int,
        *,
        only_for_sale: bool = True,
    ) -> List[ProductAccountFull]:
        stmt = (
            select(ProductAccounts)
            .options(selectinload(ProductAccounts.account_storage))
            .where(ProductAccounts.category_id == category_id)
        )
        if only_for_sale:
            stmt = stmt.join(ProductAccounts.account_storage).where(
                AccountStorage.status == StorageStatus.FOR_SALE
            )

        result = await self.session_db.execute(stmt)
        products = list(result.scalars().all())
        return [
            ProductAccountFull.from_orm_model(product, product.account_storage)
            for product in products
        ]

    async def get_by_category_id(
        self,
        category_id: int,
        *,
        only_for_sale: bool = True,
        with_storage: bool = False,
    ) -> List[ProductAccountSmall]:
        stmt = select(ProductAccounts).where(ProductAccounts.category_id == category_id)

        if only_for_sale:
            stmt = stmt.join(ProductAccounts.account_storage).where(
                AccountStorage.status == StorageStatus.FOR_SALE
            )

        if with_storage:
            stmt = stmt.options(selectinload(ProductAccounts.account_storage))

        result = await self.session_db.execute(stmt)
        products = list(result.scalars().all())
        return [ProductAccountSmall.model_validate(product) for product in products]

    async def get_by_account_id(self, account_id: int) -> Optional[ProductAccountSmall]:
        result = await self.session_db.execute(
            select(ProductAccounts).where(ProductAccounts.account_id == account_id)
        )
        product = result.scalar_one_or_none()
        return ProductAccountSmall.model_validate(product) if product else None

    async def get_by_storage_id(self, account_storage_id: int) -> Optional[ProductAccountSmall]:
        result = await self.session_db.execute(
            select(ProductAccounts).where(ProductAccounts.account_storage_id == account_storage_id)
        )
        product = result.scalar_one_or_none()
        return ProductAccountSmall.model_validate(product) if product else None

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

    async def get_existing_storage_ids(self, storage_ids: List[int]) -> List[int]:
        if not storage_ids:
            return []
        result = await self.session_db.execute(
            select(ProductAccounts.account_storage_id).where(
                ProductAccounts.account_storage_id.in_(storage_ids)
            )
        )
        return list(result.scalars().all())

    async def create_product(self, **values) -> ProductAccountSmall:
        created = await super().create(ProductAccounts, **values)
        return ProductAccountSmall.model_validate(created)

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

    async def get_for_update_by_category(
        self,
        category_id: int,
        *,
        limit: int,
        status: StorageStatus = StorageStatus.FOR_SALE,
    ) -> List[ProductAccounts]:
        stmt = (
            select(ProductAccounts)
            .options(selectinload(ProductAccounts.account_storage))
            .join(ProductAccounts.account_storage)
            .where(
                (ProductAccounts.category_id == category_id)
                & (AccountStorage.status == status)
            )
            .order_by(ProductAccounts.created_at.desc())
            .with_for_update()
            .limit(limit)
        )
        result = await self.session_db.execute(stmt)
        return list(result.scalars().all())

    async def get_for_update_candidates(
        self,
        category_id: int,
        *,
        type_account_service: AccountServiceType,
        limit: int,
    ) -> List[ProductAccounts]:
        stmt = (
            select(ProductAccounts)
            .options(selectinload(ProductAccounts.account_storage))
            .join(ProductAccounts.account_storage)
            .where(
                (ProductAccounts.category_id == category_id)
                & (AccountStorage.type_account_service == type_account_service)
                & (AccountStorage.is_active == True)
                & (AccountStorage.is_valid == True)
                & (AccountStorage.status == StorageStatus.FOR_SALE)
            )
            .with_for_update()
            .limit(limit)
        )
        result = await self.session_db.execute(stmt)
        return list(result.scalars().all())
