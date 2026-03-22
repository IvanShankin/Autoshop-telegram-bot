from typing import Optional, List

from sqlalchemy import select, delete

from src.database.models.categories import SoldUniversal
from src.repository.database.base import DatabaseBase


class SoldUniversalRepository(DatabaseBase):

    async def get_by_id(self, sold_id: int) -> Optional[SoldUniversal]:
        result = await self.session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_id)
        )
        return result.scalar_one_or_none()

    async def get_by_owner(self, owner_id: int) -> List[SoldUniversal]:
        result = await self.session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.owner_id == owner_id)
        )
        return result.scalars().all()

    async def create_sold(self, **values) -> SoldUniversal:
        return await super().create(SoldUniversal, **values)

    async def delete(self, sold_id: int) -> None:
        await self.session_db.execute(
            delete(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_id)
        )