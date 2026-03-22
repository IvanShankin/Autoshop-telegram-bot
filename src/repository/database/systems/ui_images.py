from typing import Optional, Sequence

from sqlalchemy import delete, select, update

from src.database.models.system import UiImages
from src.repository.database.base import DatabaseBase


class UiImagesRepository(DatabaseBase):

    async def get_all(self) -> Sequence[UiImages]:
        result = await self.session_db.execute(select(UiImages))
        return result.scalars().all()

    async def get_by_key(self, key: str) -> Optional[UiImages]:
        result = await self.session_db.execute(select(UiImages).where(UiImages.key == key))
        return result.scalar_one_or_none()

    async def create_ui_image(self, **values) -> UiImages:
        return await super().create(UiImages, **values)

    async def update(self, key: str, **values) -> Optional[UiImages]:
        if not values:
            return await self.get_by_key(key)

        stmt = (
            update(UiImages)
            .where(UiImages.key == key)
            .values(**values)
            .returning(UiImages)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, key: str) -> Optional[UiImages]:
        stmt = (
            delete(UiImages)
            .where(UiImages.key == key)
            .returning(UiImages)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()
