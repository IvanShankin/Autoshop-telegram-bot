from typing import Optional, List

from sqlalchemy import select, delete

from src.database.models.categories import ProductUniversal
from src.read_models import ProductUniversalDTO
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

    async def create_product(self, **value) -> ProductUniversalDTO:
        created = await super().create(ProductUniversal, **value)
        return ProductUniversalDTO.model_validate(created)

    async def delete(self, product_id: int) -> None:
        await self.session_db.execute(
            delete(ProductUniversal)
            .where(ProductUniversal.product_universal_id == product_id)
        )
