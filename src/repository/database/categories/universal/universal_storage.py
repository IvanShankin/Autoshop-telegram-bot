from typing import Optional, List, Any

from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from src.database.models.categories import (
    UniversalStorage,
)
from src.models.read_models import UniversalStorageDTO
from src.repository.database.base import DatabaseBase


class UniversalStorageRepository(DatabaseBase):

    async def get_by_id(
        self,
        universal_storage_id: int,
        with_relations: bool = False
    ) -> Optional[UniversalStorageDTO]:
        """
        :return: С подгруженными полями `product`, `sold_universal` и `translations`
        """
        stmt = select(UniversalStorage).where(
            UniversalStorage.universal_storage_id == universal_storage_id
        )

        if with_relations:
            stmt = stmt.options(
                selectinload(UniversalStorage.product),
                selectinload(UniversalStorage.sold_universal),
                selectinload(UniversalStorage.translations),
            )

        result = await self.session_db.execute(stmt)
        storage = result.scalar_one_or_none()
        return UniversalStorageDTO.model_validate(storage) if storage else None

    async def create_storage(self, **values) -> UniversalStorageDTO:
        created = await super().create(UniversalStorage, **values)
        return UniversalStorageDTO.model_validate(created)

    async def update(
        self,
        universal_storage_id: int,
        **values: Any,
    ) -> Optional[UniversalStorageDTO]:
        """
        :return: С подгруженными полями `sold_universal` и `translations`
        """
        if not values:
            return None

        await self.session_db.execute(
            update(UniversalStorage)
            .where(UniversalStorage.universal_storage_id == universal_storage_id)
            .values(**values)
        )

        result = await self.session_db.execute(
            select(UniversalStorage)
            .options(
                selectinload(UniversalStorage.product),
                selectinload(UniversalStorage.sold_universal),
                selectinload(UniversalStorage.translations),
            )
            .where(UniversalStorage.universal_storage_id == universal_storage_id)
        )
        storage = result.scalar_one_or_none()
        return UniversalStorageDTO.model_validate(storage) if storage else None

    async def delete_by_ids(self, storage_ids: List[int]) -> List[UniversalStorageDTO]:
        result = await self.session_db.execute(
            delete(UniversalStorage)
            .where(UniversalStorage.universal_storage_id.in_(storage_ids))
            .returning(UniversalStorage)
        )
        deleted = list(result.scalars().all())
        return [UniversalStorageDTO.model_validate(item) for item in deleted]
