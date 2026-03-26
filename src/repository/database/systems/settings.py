from typing import Optional

from sqlalchemy import select, update

from src.database.models.system import Settings
from src.models.read_models.other import SettingsDTO
from src.repository.database.base import DatabaseBase


class SettingsRepository(DatabaseBase):

    async def get(self) -> Optional[SettingsDTO]:
        result = await self.session_db.execute(select(Settings))
        settings = result.scalars().first()
        return SettingsDTO.model_validate(settings) if settings else None

    async def update(self, **values) -> Optional[SettingsDTO]:
        if not values:
            return await self.get()

        stmt = update(Settings).values(**values).returning(Settings)
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return SettingsDTO.model_validate(updated) if updated else None
