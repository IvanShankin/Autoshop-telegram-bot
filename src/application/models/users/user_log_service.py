from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.users import CreateUserAuditLogDTO
from src.models.read_models.other import UserAuditLogsDTO
from src.repository.database.users import UserAuditLogsRepository


class UserLogService:

    def __init__(self, log_repo: UserAuditLogsRepository, session_db: AsyncSession):
        self.log_repo = log_repo
        self.session_db = session_db

    async def create_log(
        self,
        user_id: int,
        data: CreateUserAuditLogDTO,
        make_commit: Optional[bool] = False
    ) -> UserAuditLogsDTO:
        values = data.model_dump()
        log = await self.log_repo.create_log(user_id=user_id, **values)

        if make_commit:
            await self.session_db.commit()

        return log

    async def get_all_by_user(self, user_id: int) -> Sequence[UserAuditLogsDTO]:
        return await self.log_repo.get_all_by_user(user_id)