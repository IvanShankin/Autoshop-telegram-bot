from typing import Optional

from sqlalchemy import delete, select

from src.database.models.system import BackupLogs
from src.repository.database.base import DatabaseBase


class BackupLogsRepository(DatabaseBase):

    async def get_by_id(self, backup_log_id: int) -> Optional[BackupLogs]:
        result = await self.session_db.execute(
            select(BackupLogs).where(BackupLogs.backup_log_id == backup_log_id)
        )
        return result.scalar_one_or_none()

    async def get_all_desc(self):
        result = await self.session_db.execute(
            select(BackupLogs).order_by(BackupLogs.created_at.desc())
        )
        return result.scalars().all()

    async def create_backup_log(self, **values) -> BackupLogs:
        return await super().create(BackupLogs, **values)

    async def delete(self, backup_log_id: int) -> Optional[BackupLogs]:
        stmt = (
            delete(BackupLogs)
            .where(BackupLogs.backup_log_id == backup_log_id)
            .returning(BackupLogs)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()