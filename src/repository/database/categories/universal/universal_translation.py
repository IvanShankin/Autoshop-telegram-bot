from typing import Optional, List, Any

from sqlalchemy import select, update

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
                (UniversalStorageTranslation.language == language)
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

    async def exists(self, universal_storage_id: int, language: str) -> bool:
        result = await self.session_db.execute(
            select(UniversalStorageTranslation.universal_storage_translations_id).where(
                (UniversalStorageTranslation.universal_storage_id == universal_storage_id)
                & (UniversalStorageTranslation.language == language)
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_translate(
        self,
        **values
    ) -> UniversalStorageTranslationDTO:
        created = await super().create(UniversalStorageTranslation, **values)
        return UniversalStorageTranslationDTO.model_validate(created)

    async def update(
        self,
        universal_storage_id: int,
        language: str,
        **values: Any,
    ) -> Optional[UniversalStorageTranslationDTO]:
        if not values:
            return await self.get(universal_storage_id, language)

        result = await self.session_db.execute(
            update(UniversalStorageTranslation)
            .where(
                (UniversalStorageTranslation.universal_storage_id == universal_storage_id)
                & (UniversalStorageTranslation.language == language)
            )
            .values(**values)
            .returning(UniversalStorageTranslation)
        )
        translation = result.scalar_one_or_none()
        return UniversalStorageTranslationDTO.model_validate(translation) if translation else None
