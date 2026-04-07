from typing import List, Optional

from sqlalchemy import delete, select

from src.database.models.users import (
    BannedAccounts,
)
from src.models.read_models.other import BannedAccountsDTO
from src.repository.database.base import DatabaseBase


class BannedAccountsRepository(DatabaseBase):
    async def get_by_user_id(self, user_id: int) -> Optional[BannedAccountsDTO]:
        result = await self.session_db.execute(
            select(BannedAccounts).where(BannedAccounts.user_id == user_id)
        )
        result_ban = result.scalar_one_or_none()
        return BannedAccountsDTO.model_validate(result_ban) if result_ban else None

    async def create_ban(self, **values) -> BannedAccountsDTO:
        created = await super().create(BannedAccounts, **values)
        return BannedAccountsDTO.model_validate(created)

    async def delete_by_user_id(self, user_id: int) -> Optional[BannedAccountsDTO]:
        stmt = (
            delete(BannedAccounts)
            .where(BannedAccounts.user_id == user_id)
            .returning(BannedAccounts)
        )
        result = await self.session_db.execute(stmt)
        deleted = result.scalar_one_or_none()
        return BannedAccountsDTO.model_validate(deleted) if deleted else None

    async def get_all(self) -> List[BannedAccountsDTO]:
        result = await self.session_db.execute(select(BannedAccounts))
        accounts = list(result.scalars().all())
        return [BannedAccountsDTO.model_validate(account) for account in accounts]
