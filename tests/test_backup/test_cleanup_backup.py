import pytest
from sqlalchemy import select

from src.services.database.backups.backup_db import cleanup_old_backups
from src.services.database.core import get_db
from src.services.database.system.models import BackupLogs


@pytest.mark.asyncio
async def test_cleanup_no_action_when_not_exceeding(monkeypatch, create_backup_log, fake_storage):
    """Не должен удалить бэкапы, т.к. их недостаточно"""
    await create_backup_log()
    await create_backup_log()

    await cleanup_old_backups(retain_last=2)

    fake_storage.purge_secret.assert_not_called()
    async with get_db() as session_db:
        result = await session_db.execute(select(BackupLogs))
        assert len(result.scalars().all()) == 2


@pytest.mark.asyncio
async def test_cleanup_deletes_old_backups(monkeypatch, create_backup_log, fake_storage):
    for i in range(4):
        await create_backup_log()

    await cleanup_old_backups(retain_last=2)

    # Удаляем 2 последних бэкапа (останется 2)
    async with get_db() as session_db:
        result_db = await session_db.execute(select(BackupLogs))
        result = result_db.scalars().all()
        assert len(result) == 2
