from typing import Optional

from sqlalchemy import select, update

from src.database.models.system.models import Files
from src.repository.database.base import DatabaseBase


class FilesRepository(DatabaseBase):

    async def get_by_key(self, key: str) -> Optional[Files]:
        result = await self.session_db.execute(select(Files).where(Files.key == key))
        return result.scalar_one_or_none()

    async def create_file(self, **values) -> Files:
        return await super().create(Files, **values)

    async def update(self, key: str, **values) -> Optional[Files]:
        if not values:
            return await self.get_by_key(key)

        stmt = (
            update(Files)
            .where(Files.key == key)
            .values(**values)
            .returning(Files)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()