from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.system import CreateBackupLogDTO
from src.models.read_models.other import BackupLogsDTO
from src.repository.database.systems import BackupLogsRepository


class BackupLogsService:

    def __init__(self, backup_logs_repo: BackupLogsRepository, session_db: AsyncSession):
        self.backup_logs_repo = backup_logs_repo
        self.session_db = session_db

    async def add_backup_log(
        self,
        data: CreateBackupLogDTO,
        make_commit: Optional[bool] = False,
    ) -> BackupLogsDTO:
        values = data.model_dump()
        log = await self.backup_logs_repo.create_backup_log(**values)

        if make_commit:
            await self.session_db.commit()

        return log

    async def get_backup_log_by_id(self, backup_log_id: int) -> Optional[BackupLogsDTO]:
        return await self.backup_logs_repo.get_by_id(backup_log_id)

    async def get_all_backup_logs_desc(self) -> Sequence[BackupLogsDTO]:
        return await self.backup_logs_repo.get_all_desc()

    async def delete_backup_log(
        self,
        backup_log_id: int,
        make_commit: Optional[bool] = False,
    ) -> Optional[BackupLogsDTO]:
        deleted = await self.backup_logs_repo.delete(backup_log_id)

        if make_commit:
            await self.session_db.commit()

        return deleted
