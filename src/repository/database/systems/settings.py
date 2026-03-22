from typing import Optional

from sqlalchemy import select, update

from src.database.models.system import Settings
from src.repository.database.base import DatabaseBase


class SettingsRepository(DatabaseBase):

    async def get(self) -> Optional[Settings]:
        result = await self.session_db.execute(select(Settings))
        return result.scalars().first()

    async def update(self, **values) -> Optional[Settings]:
        if not values:
            return await self.get()

        stmt = update(Settings).values(**values).returning(Settings)
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()