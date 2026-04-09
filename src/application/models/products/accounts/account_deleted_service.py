from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.accounts import CreateDeletedAccountDTO
from src.models.read_models import DeletedAccountsDTO
from src.repository.database.categories.accounts import DeletedAccountsRepository


class AccountDeletedService:

    def __init__(
        self,
        deleted_repo: DeletedAccountsRepository,
        session_db: AsyncSession,
    ):
        self.deleted_repo = deleted_repo
        self.session_db = session_db

    async def get_deleted_account(self, deleted_account_id: int) -> DeletedAccountsDTO | None:
        return await self.deleted_repo.get_by_id(deleted_account_id)

    async def get_deleted_account_by_storage_id(self, account_storage_id: int) -> DeletedAccountsDTO | None:
        return await self.deleted_repo.get_by_account_storage_id(account_storage_id)

    async def create_deleted_account(
        self,
        data: CreateDeletedAccountDTO,
        make_commit: Optional[bool] = True,
    ) -> DeletedAccountsDTO:
        deleted = await self.deleted_repo.create_deleted(**data.model_dump(exclude_unset=True))
        if make_commit:
            await self.session_db.commit()
        return deleted
