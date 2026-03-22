from typing import Sequence

from sqlalchemy import select

from src.database.models.users import (
    UserAuditLogs,
)
from src.repository.database.base import DatabaseBase


class UserAuditLogsRepository(DatabaseBase):
    async def get_all_by_user(self, user_id: int) -> Sequence[UserAuditLogs]:
        result = await self.session_db.execute(
            select(UserAuditLogs)
            .where(UserAuditLogs.user_id == user_id)
            .order_by(UserAuditLogs.created_at.desc())
        )
        return result.scalars().all()

    async def create_log(self, **values) -> UserAuditLogs:
        return await super().create(UserAuditLogs, **values)