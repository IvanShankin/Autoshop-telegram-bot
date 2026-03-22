from typing import Optional

from sqlalchemy import select, update

from src.database.models.users import Replenishments
from src.repository.database.base import DatabaseBase


class ReplenishmentsRepository(DatabaseBase):

    async def get_by_id(self, replenishment_id: int) -> Optional[Replenishments]:
        result = await self.session_db.execute(
            select(Replenishments).where(Replenishments.replenishment_id == replenishment_id)
        )
        return result.scalar_one_or_none()

    async def create_replenishment(self, **values) -> Replenishments:
        return await super().create(Replenishments, **values)

    async def update(self, replenishment_id: int, **values) -> Optional[Replenishments]:
        if not values:
            return await self.get_by_id(replenishment_id)

        stmt = (
            update(Replenishments)
            .where(Replenishments.replenishment_id == replenishment_id)
            .values(**values)
            .returning(Replenishments)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()