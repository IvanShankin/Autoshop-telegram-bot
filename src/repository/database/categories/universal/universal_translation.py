from typing import Optional, List

from sqlalchemy import select

from src.database.models.categories import UniversalStorageTranslation
from src.repository.database.base import DatabaseBase


class UniversalTranslationRepository(DatabaseBase):

    async def get(
        self,
        universal_storage_id: int,
        language: str
    ) -> Optional[UniversalStorageTranslation]:
        result = await self.session_db.execute(
            select(UniversalStorageTranslation).where(
                (UniversalStorageTranslation.universal_storage_id == universal_storage_id) &
                (UniversalStorageTranslation.lang == language)
            )
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        universal_storage_id: int
    ) -> List[UniversalStorageTranslation]:
        result = await self.session_db.execute(
            select(UniversalStorageTranslation)
            .where(UniversalStorageTranslation.universal_storage_id == universal_storage_id)
        )
        return result.scalars().all()

    async def create_translate(
        self,
        **values
    ) -> UniversalStorageTranslation:
        return await super().create(UniversalStorageTranslation, **values)