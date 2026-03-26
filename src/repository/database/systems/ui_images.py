from typing import Optional, Sequence

from sqlalchemy import delete, select, update

from src.database.models.system import UiImages
from src.models.read_models.other import UiImagesDTO
from src.repository.database.base import DatabaseBase


class UiImagesRepository(DatabaseBase):

    async def get_all(self) -> Sequence[UiImagesDTO]:
        result = await self.session_db.execute(select(UiImages))
        images = list(result.scalars().all())
        return [UiImagesDTO.model_validate(image) for image in images]

    async def get_by_key(self, key: str) -> Optional[UiImagesDTO]:
        result = await self.session_db.execute(select(UiImages).where(UiImages.key == key))
        image = result.scalar_one_or_none()
        return UiImagesDTO.model_validate(image) if image else None

    async def create_ui_image(self, **values) -> UiImagesDTO:
        created = await super().create(UiImages, **values)
        return UiImagesDTO.model_validate(created)

    async def update(self, key: str, **values) -> Optional[UiImagesDTO]:
        if not values:
            return await self.get_by_key(key)

        stmt = (
            update(UiImages)
            .where(UiImages.key == key)
            .values(**values)
            .returning(UiImages)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return UiImagesDTO.model_validate(updated) if updated else None

    async def delete(self, key: str) -> Optional[UiImagesDTO]:
        stmt = (
            delete(UiImages)
            .where(UiImages.key == key)
            .returning(UiImages)
        )
        result = await self.session_db.execute(stmt)
        deleted = result.scalar_one_or_none()
        return UiImagesDTO.model_validate(deleted) if deleted else None
