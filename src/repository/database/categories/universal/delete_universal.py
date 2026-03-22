from src.database.models.categories import DeletedUniversal
from src.repository.database.base import DatabaseBase


class DeletedUniversalRepository(DatabaseBase):

    async def create_deleted(self, **values) -> DeletedUniversal:
        return await super().create(DeletedUniversal, **values)