from typing import Sequence

from sqlalchemy import select

from src.database.models.users import (
    UserAuditLogs,
)
from src.models.read_models.other import UserAuditLogsDTO
from src.repository.database.base import DatabaseBase


class UserAuditLogsRepository(DatabaseBase):
    async def get_all_by_user(self, user_id: int) -> Sequence[UserAuditLogsDTO]:
        result = await self.session_db.execute(
            select(UserAuditLogs)
            .where(UserAuditLogs.user_id == user_id)
            .order_by(UserAuditLogs.created_at.desc())
        )
        logs = list(result.scalars().all())
        return [UserAuditLogsDTO.model_validate(log) for log in logs]

    async def create_log(self, **values) -> UserAuditLogsDTO:
        created = await super().create(UserAuditLogs, **values)
        return UserAuditLogsDTO.model_validate(created)
