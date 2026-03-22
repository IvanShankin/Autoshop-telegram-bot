from typing import Optional, List

from sqlalchemy import select, delete

from src.database.models.categories import ProductUniversal
from src.repository.database.base import DatabaseBase


class ProductUniversalRepository(DatabaseBase):

    async def get_by_id(self, product_id: int) -> Optional[ProductUniversal]:
        result = await self.session_db.execute(
            select(ProductUniversal)
            .where(ProductUniversal.product_universal_id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_by_category(self, category_id: int) -> List[ProductUniversal]:
        result = await self.session_db.execute(
            select(ProductUniversal)
            .where(ProductUniversal.category_id == category_id)
        )
        return result.scalars().all()

    async def create_product(self, **value) -> ProductUniversal:
        return await super().create(ProductUniversal, **value)

    async def delete(self, product_id: int) -> None:
        await self.session_db.execute(
            delete(ProductUniversal)
            .where(ProductUniversal.product_universal_id == product_id)
        )