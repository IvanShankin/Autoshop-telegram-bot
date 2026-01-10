import asyncio
import os
import tempfile
from datetime import datetime, UTC
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import get_config
from src.services.database.system.actions.actions import add_backup_log, get_all_backup_logs_desc, delete_backup_log
from src.services.secrets import get_crypto_context
from src.services.secrets.encrypt import encrypt_dump_file, wrap_dek
from src.services.secrets.loader import get_storage_client
from src.services.secrets.utils import extract_nonce_b64, calc_sha256_b64
from src.utils.core_logger import get_logger


def add_backup_create(scheduler: AsyncIOScheduler) -> AsyncIOScheduler:
    scheduler.add_job(
        backup_database,
        trigger=CronTrigger(hour=4, minute=30),
        id="daily_db_backup",
        replace_existing=True,
    )
    return scheduler


def add_backup_cleanup(scheduler: AsyncIOScheduler) -> AsyncIOScheduler:
    scheduler.add_job(
        cleanup_old_backups,
        trigger=CronTrigger(hour=5, minute=0),
        id="cleanup_old_backups",
        replace_existing=True,
    )
    return scheduler



async def dump_postgres_db(
    db_name: str,
    db_user: str,
    db_password: str,
    db_host: str,
    output_file: Path,
):
    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    process = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-h", db_host,
        "-U", db_user,
        "-F", "c",          # custom format (лучше для восстановления)
        "-f", str(output_file),
        db_name,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(
            f"pg_dump failed: {stderr.decode()}"
        )


async def backup_database():
    config = get_config()
    crypto = get_crypto_context()

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        enc_name = f"db_{timestamp}.enc"
        enc_name_secret = f"dump_db:{timestamp}"

        dump_file = tmpdir / f"db_{timestamp}.dump"
        encrypted_file = tmpdir / enc_name

        dek = os.urandom(32)

        encrypted_dek_b64, dek_nonce_b64, dek_sha256_b64 = wrap_dek(
            dek=dek,
            kek=crypto.kek
        )

        await dump_postgres_db(
            db_name=config.env.db_name,
            db_user=config.env.db_user,
            db_password=config.secrets.db_password,
            db_host=config.env.db_host,
            output_file=dump_file,
        )

        encrypt_dump_file(
            dump_path=dump_file,
            encrypted_path=encrypted_file,
            dek=dek,
        )

        # SHA256 + nonce для файла
        nonce_b64 = extract_nonce_b64(encrypted_file)
        sha256_b64 = calc_sha256_b64(encrypted_file)

        size_bytes = encrypted_file.stat().st_size

        storage = get_storage_client()

        # Сохраняем DEK в storage
        storage.create_secret_string(
            name=enc_name_secret,
            encrypted_data=encrypted_dek_b64,
            nonce=dek_nonce_b64,
            sha256=dek_sha256_b64,
        )

        storage.upload_secret_file(
            name=enc_name,
            file_path=encrypted_file,
            nonce_b64=nonce_b64,
            sha256_b64=sha256_b64,
        )

        await add_backup_log(
            storage_file_name=enc_name,
            storage_encrypted_dek_name=enc_name_secret,
            encrypted_dek_b64=encrypted_dek_b64,
            dek_nonce_b64=dek_nonce_b64,
            size_bytes=size_bytes,
        )


async def cleanup_old_backups(retain_last: int = 2):
    storage = get_storage_client()
    logger = get_logger(__name__)
    backups = await get_all_backup_logs_desc()  # DESC

    if backups is None or len(backups) <= retain_last:
        return

    to_delete = backups[retain_last:]

    for backup in to_delete:
        # удалить файл бэкапа
        try:
            storage.purge_secret(backup.storage_file_name)
        except Exception:
            logger.exception("Failed to purge backup %s", backup.storage_file_name)

        try:
            # удалить зашифрованный DEK
            storage.purge_secret(backup.storage_encrypted_dek_name)
        except Exception:
            logger.exception("Failed to purge dek for backup %s", backup.storage_encrypted_dek_name)

        await delete_backup_log(backup.backup_log_id)
