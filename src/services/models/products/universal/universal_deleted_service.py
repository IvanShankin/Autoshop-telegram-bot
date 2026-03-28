from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.universal import CreateDeletedUniversalDTO
from src.models.read_models import DeletedUniversalDTO
from src.repository.database.categories.universal import DeletedUniversalRepository


class UniversalDeletedService:

    def __init__(
        self,
        deleted_repo: DeletedUniversalRepository,
        session_db: AsyncSession,
    ):
        self.deleted_repo = deleted_repo
        self.session_db = session_db

    async def get_deleted_universal(self, deleted_universal_id: int) -> DeletedUniversalDTO | None:
        return await self.deleted_repo.get_by_id(deleted_universal_id)

    async def create_deleted_universal(
        self,
        data: CreateDeletedUniversalDTO,
        make_commit: bool = True,
    ) -> DeletedUniversalDTO:
        deleted = await self.deleted_repo.create_deleted(**data.model_dump(exclude_unset=True))
        if make_commit:
            await self.session_db.commit()
        return deleted
