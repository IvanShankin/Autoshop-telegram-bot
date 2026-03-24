from src.database.models.categories import DeletedUniversal
from src.read_models import DeletedUniversalDTO
from src.repository.database.base import DatabaseBase


class DeletedUniversalRepository(DatabaseBase):

    async def create_deleted(self, **values) -> DeletedUniversalDTO:
        created = await super().create(DeletedUniversal, **values)
        return DeletedUniversalDTO.model_validate(created)
