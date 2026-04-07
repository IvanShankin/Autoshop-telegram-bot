from typing import Optional, List

from sqlalchemy import delete, select, update

from src.database.models.system.models import Stickers
from src.models.read_models.other import StickersDTO
from src.repository.database.base import DatabaseBase


class StickersRepository(DatabaseBase):

    async def get_by_key(self, key: str) -> Optional[StickersDTO]:
        result = await self.session_db.execute(select(Stickers).where(Stickers.key == key))
        sticker = result.scalar_one_or_none()
        return StickersDTO.model_validate(sticker) if sticker else None

    async def get_all(self) -> List[StickersDTO]:
        result = await self.session_db.execute(select(Stickers))
        stickers = result.scalars()
        return [StickersDTO.model_validate(sticker) for sticker in stickers]

    async def create_sticker(self, **values) -> StickersDTO:
        created = await super().create(Stickers, **values)
        return StickersDTO.model_validate(created)

    async def update(self, key: str, **values) -> Optional[StickersDTO]:
        if not values:
            return await self.get_by_key(key)

        stmt = (
            update(Stickers)
            .where(Stickers.key == key)
            .values(**values)
            .returning(Stickers)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return StickersDTO.model_validate(updated) if updated else None

    async def delete(self, key: str) -> Optional[StickersDTO]:
        stmt = (
            delete(Stickers)
            .where(Stickers.key == key)
            .returning(Stickers)
        )
        result = await self.session_db.execute(stmt)
        deleted = result.scalar_one_or_none()
        return StickersDTO.model_validate(deleted) if deleted else None
