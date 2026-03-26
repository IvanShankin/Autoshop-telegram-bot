from typing import Optional, List

from sqlalchemy import select

from src.database.models.categories import UniversalStorageTranslation
from src.models.read_models import UniversalStorageTranslationDTO
from src.repository.database.base import DatabaseBase


class UniversalTranslationRepository(DatabaseBase):

    async def get(
        self,
        universal_storage_id: int,
        language: str
    ) -> Optional[UniversalStorageTranslationDTO]:
        result = await self.session_db.execute(
            select(UniversalStorageTranslation).where(
                (UniversalStorageTranslation.universal_storage_id == universal_storage_id) &
                (UniversalStorageTranslation.lang == language)
            )
        )
        translation = result.scalar_one_or_none()
        return UniversalStorageTranslationDTO.model_validate(translation) if translation else None

    async def get_all(
        self,
        universal_storage_id: int
    ) -> List[UniversalStorageTranslationDTO]:
        result = await self.session_db.execute(
            select(UniversalStorageTranslation)
            .where(UniversalStorageTranslation.universal_storage_id == universal_storage_id)
        )
        translations = list(result.scalars().all())
        return [UniversalStorageTranslationDTO.model_validate(t) for t in translations]

    async def create_translate(
        self,
        **values
    ) -> UniversalStorageTranslationDTO:
        created = await super().create(UniversalStorageTranslation, **values)
        return UniversalStorageTranslationDTO.model_validate(created)
