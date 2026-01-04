import inspect
from pathlib import Path

import pytest

from sqlalchemy import select

from src.deferred_tasks.core import init_scheduler
from src.services.database.backups.backup_db import backup_database, add_backup_create
from src.services.database.core import get_db
from src.services.database.system.models import BackupLogs


@pytest.mark.asyncio
async def test_backup_database_happy_path(
    fake_storage,
    monkeypatch
):
    async def fake_dump_postgres_db(*, output_file: Path, **kwargs):
        output_file.write_bytes(b"FAKE_DB_DUMP")

    from src.services.database.backups import backup_db as core_modul
    monkeypatch.setattr(
        core_modul,
        "dump_postgres_db",
        fake_dump_postgres_db
    )

    await backup_database()

    # Проверяем, что DEK сохранён
    fake_storage.create_secret_string.assert_called_once()
    fake_storage.upload_secret_file.assert_called_once()

    # Проверяем лог в БД
    async with get_db() as session_db:
        result_db = await session_db.execute(select(BackupLogs))
        assert result_db.scalars().first()


@pytest.mark.asyncio
async def test_init_backup_scheduler():
    scheduler = init_scheduler()
    add_backup_create(scheduler)

    jobs = scheduler.get_jobs()
    assert len(jobs) == 1

    job = jobs[0]
    assert job.id == "daily_db_backup"
    assert inspect.iscoroutinefunction(job.func)
