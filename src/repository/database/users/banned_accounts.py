from typing import Optional

from sqlalchemy import delete, select

from src.database.models.users import (
    BannedAccounts,
)
from src.repository.database.base import DatabaseBase


class BannedAccountsRepository(DatabaseBase):
    async def get_by_user_id(self, user_id: int) -> Optional[BannedAccounts]:
        result = await self.session_db.execute(
            select(BannedAccounts).where(BannedAccounts.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_ban(self, **values) -> BannedAccounts:
        return await super().create(BannedAccounts, **values)

    async def delete_by_user_id(self, user_id: int) -> Optional[BannedAccounts]:
        stmt = (
            delete(BannedAccounts)
            .where(BannedAccounts.user_id == user_id)
            .returning(BannedAccounts)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()