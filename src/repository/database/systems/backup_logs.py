from typing import Optional

from sqlalchemy import delete, select

from src.database.models.system import BackupLogs
from src.read_models.other import BackupLogsDTO
from src.repository.database.base import DatabaseBase


class BackupLogsRepository(DatabaseBase):

    async def get_by_id(self, backup_log_id: int) -> Optional[BackupLogsDTO]:
        result = await self.session_db.execute(
            select(BackupLogs).where(BackupLogs.backup_log_id == backup_log_id)
        )
        log = result.scalar_one_or_none()
        return BackupLogsDTO.model_validate(log) if log else None

    async def get_all_desc(self) -> list[BackupLogsDTO]:
        result = await self.session_db.execute(
            select(BackupLogs).order_by(BackupLogs.created_at.desc())
        )
        logs = list(result.scalars().all())
        return [BackupLogsDTO.model_validate(log) for log in logs]

    async def create_backup_log(self, **values) -> BackupLogsDTO:
        created = await super().create(BackupLogs, **values)
        return BackupLogsDTO.model_validate(created)

    async def delete(self, backup_log_id: int) -> Optional[BackupLogsDTO]:
        stmt = (
            delete(BackupLogs)
            .where(BackupLogs.backup_log_id == backup_log_id)
            .returning(BackupLogs)
        )
        result = await self.session_db.execute(stmt)
        deleted = result.scalar_one_or_none()
        return BackupLogsDTO.model_validate(deleted) if deleted else None
