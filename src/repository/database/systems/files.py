from typing import Optional

from sqlalchemy import select, update

from src.database.models.system.models import Files
from src.models.read_models.other import FilesDTO
from src.repository.database.base import DatabaseBase


class FilesRepository(DatabaseBase):

    async def get_by_key(self, key: str) -> Optional[FilesDTO]:
        result = await self.session_db.execute(select(Files).where(Files.key == key))
        file_obj = result.scalar_one_or_none()
        return FilesDTO.model_validate(file_obj) if file_obj else None

    async def create_file(self, **values) -> FilesDTO:
        created = await super().create(Files, **values)
        return FilesDTO.model_validate(created)

    async def update(self, key: str, **values) -> Optional[FilesDTO]:
        if not values:
            return await self.get_by_key(key)

        stmt = (
            update(Files)
            .where(Files.key == key)
            .values(**values)
            .returning(Files)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return FilesDTO.model_validate(updated) if updated else None
