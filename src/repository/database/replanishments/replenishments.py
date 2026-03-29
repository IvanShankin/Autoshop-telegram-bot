from typing import Optional

from sqlalchemy import select, update

from src.database.models.users import Replenishments
from src.models.read_models.other import ReplenishmentsDTO
from src.repository.database.base import DatabaseBase


class ReplenishmentsRepository(DatabaseBase):

    async def get_by_id(self, replenishment_id: int) -> Optional[ReplenishmentsDTO]:
        result = await self.session_db.execute(
            select(Replenishments).where(Replenishments.replenishment_id == replenishment_id)
        )
        replenishment = result.scalar_one_or_none()
        return ReplenishmentsDTO.model_validate(replenishment) if replenishment else None

    async def get_by_id_for_update(self, replenishment_id: int) -> Optional[Replenishments]:
        result = await self.session_db.execute(
            select(Replenishments)
            .where(Replenishments.replenishment_id == replenishment_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create_replenishment(self, **values) -> ReplenishmentsDTO:
        created = await super().create(Replenishments, **values)
        return ReplenishmentsDTO.model_validate(created)

    async def update(self, replenishment_id: int, **values) -> Optional[ReplenishmentsDTO]:
        if not values:
            return await self.get_by_id(replenishment_id)

        stmt = (
            update(Replenishments)
            .where(Replenishments.replenishment_id == replenishment_id)
            .values(**values)
            .returning(Replenishments)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return ReplenishmentsDTO.model_validate(updated) if updated else None
