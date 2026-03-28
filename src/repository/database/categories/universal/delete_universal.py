from typing import Optional

from sqlalchemy import select

from src.database.models.categories import DeletedUniversal
from src.models.read_models import DeletedUniversalDTO
from src.repository.database.base import DatabaseBase


class DeletedUniversalRepository(DatabaseBase):

    async def get_by_id(self, deleted_universal_id: int) -> Optional[DeletedUniversalDTO]:
        result = await self.session_db.execute(
            select(DeletedUniversal).where(
                DeletedUniversal.deleted_universal_id == deleted_universal_id
            )
        )
        deleted = result.scalar_one_or_none()
        return DeletedUniversalDTO.model_validate(deleted) if deleted else None

    async def create_deleted(self, **values) -> DeletedUniversalDTO:
        created = await super().create(DeletedUniversal, **values)
        return DeletedUniversalDTO.model_validate(created)
