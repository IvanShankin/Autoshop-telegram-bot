from typing import Optional

from sqlalchemy import delete, select, update

from src.database.models.system.models import Stickers
from src.repository.database.base import DatabaseBase


class StickersRepository(DatabaseBase):

    async def get_by_key(self, key: str) -> Optional[Stickers]:
        result = await self.session_db.execute(select(Stickers).where(Stickers.key == key))
        return result.scalar_one_or_none()

    async def create_sticker(self, **values) -> Stickers:
        return await super().create(Stickers, **values)

    async def update(self, key: str, **values) -> Optional[Stickers]:
        if not values:
            return await self.get_by_key(key)

        stmt = (
            update(Stickers)
            .where(Stickers.key == key)
            .values(**values)
            .returning(Stickers)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, key: str) -> Optional[Stickers]:
        stmt = (
            delete(Stickers)
            .where(Stickers.key == key)
            .returning(Stickers)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()
