from typing import Optional, List

from sqlalchemy import select, delete

from src.database.models.categories import SoldUniversal
from src.models.read_models import SoldUniversalDTO
from src.repository.database.base import DatabaseBase


class SoldUniversalRepository(DatabaseBase):

    async def get_by_id(self, sold_id: int) -> Optional[SoldUniversalDTO]:
        result = await self.session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_id)
        )
        sold = result.scalar_one_or_none()
        return SoldUniversalDTO.model_validate(sold) if sold else None

    async def get_by_owner(self, owner_id: int) -> List[SoldUniversalDTO]:
        result = await self.session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.owner_id == owner_id)
        )
        sold_items = list(result.scalars().all())
        return [SoldUniversalDTO.model_validate(item) for item in sold_items]

    async def create_sold(self, **values) -> SoldUniversalDTO:
        created = await super().create(SoldUniversal, **values)
        return SoldUniversalDTO.model_validate(created)

    async def delete(self, sold_id: int) -> None:
        await self.session_db.execute(
            delete(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_id)
        )
