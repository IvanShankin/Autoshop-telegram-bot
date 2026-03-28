from typing import Optional, List

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from src.database.models.categories import ProductUniversal, UniversalStorage, StorageStatus
from src.models.read_models import ProductUniversalDTO, ProductUniversalFull
from src.repository.database.base import DatabaseBase


class ProductUniversalRepository(DatabaseBase):

    async def get_by_id(self, product_id: int) -> Optional[ProductUniversalDTO]:
        result = await self.session_db.execute(
            select(ProductUniversal)
            .where(ProductUniversal.product_universal_id == product_id)
        )
        product = result.scalar_one_or_none()
        return ProductUniversalDTO.model_validate(product) if product else None

    async def get_by_category(self, category_id: int) -> List[ProductUniversalDTO]:
        result = await self.session_db.execute(
            select(ProductUniversal)
            .where(ProductUniversal.category_id == category_id)
        )
        products = list(result.scalars().all())
        return [ProductUniversalDTO.model_validate(product) for product in products]

    async def get_by_category_for_sale(self, category_id: int) -> List[ProductUniversalDTO]:
        result = await self.session_db.execute(
            select(ProductUniversal)
            .join(ProductUniversal.storage)
            .where(
                (ProductUniversal.category_id == category_id)
                & (UniversalStorage.status == StorageStatus.FOR_SALE)
            )
        )
        products = list(result.scalars().all())
        return [ProductUniversalDTO.model_validate(product) for product in products]

    async def get_full_by_id(
        self,
        product_id: int,
        *,
        language: str,
    ) -> Optional[ProductUniversalFull]:
        result = await self.session_db.execute(
            select(ProductUniversal)
            .options(
                selectinload(ProductUniversal.storage)
                .selectinload(UniversalStorage.translations)
            )
            .where(ProductUniversal.product_universal_id == product_id)
        )
        product = result.scalar_one_or_none()
        return ProductUniversalFull.from_orm_model(product, language) if product else None

    async def get_full_by_category(
        self,
        category_id: int,
        *,
        language: str,
        only_for_sale: bool = True,
    ) -> List[ProductUniversalFull]:
        stmt = (
            select(ProductUniversal)
            .options(
                selectinload(ProductUniversal.storage)
                .selectinload(UniversalStorage.translations)
            )
            .where(ProductUniversal.category_id == category_id)
        )
        if only_for_sale:
            stmt = stmt.join(ProductUniversal.storage).where(
                UniversalStorage.status == StorageStatus.FOR_SALE
            )

        result = await self.session_db.execute(stmt)
        products = list(result.scalars().all())
        return [ProductUniversalFull.from_orm_model(prod, language) for prod in products]

    async def get_ids_by_category(self, category_id: int) -> List[int]:
        result = await self.session_db.execute(
            select(ProductUniversal.product_universal_id)
            .where(ProductUniversal.category_id == category_id)
        )
        return list(result.scalars().all())

    async def get_storage_ids_by_category(self, category_id: int) -> List[int]:
        result = await self.session_db.execute(
            select(ProductUniversal.universal_storage_id)
            .where(ProductUniversal.category_id == category_id)
        )
        return list(result.scalars().all())

    async def create_product(self, **value) -> ProductUniversalDTO:
        created = await super().create(ProductUniversal, **value)
        return ProductUniversalDTO.model_validate(created)

    async def delete(self, product_id: int) -> None:
        await self.session_db.execute(
            delete(ProductUniversal)
            .where(ProductUniversal.product_universal_id == product_id)
        )
