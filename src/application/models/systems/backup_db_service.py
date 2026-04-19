import asyncio
import os
import tempfile
from datetime import datetime, UTC
from logging import Logger
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.application.crypto.crypto_context import CryptoProvider
from src.application.models.systems import BackupLogsService
from src.application.utils.date_time_formatter import DateTimeFormatter
from src.config import Config
from src.domain.crypto.encrypt import encrypt_file, wrap_dek
from src.domain.crypto.utils import extract_nonce_b64, calc_sha256_b64
from src.infrastructure.crypto.secret_storage.secrets_storage import SecretsStorage
from src.models.create_models.system import CreateBackupLogDTO


class BackupDBService:

    def __init__(
        self,
        conf: Config,
        logger: Logger,
        crypto_provider: CryptoProvider,
        secret_storage: SecretsStorage,
        backup_logs_service: BackupLogsService,
        dt_formatter: DateTimeFormatter,
    ):
        self.conf = conf
        self.logger = logger
        self.crypto_provider = crypto_provider
        self.secret_storage = secret_storage
        self.backup_logs_service = backup_logs_service
        self.dt_formatter = dt_formatter


    def add_backup_create(self, scheduler: AsyncIOScheduler) -> AsyncIOScheduler:
        scheduler.add_job(
            self.backup_database,
            trigger=CronTrigger(hour=4, minute=30),
            id="daily_db_backup",
            replace_existing=True,
        )
        return scheduler


    def add_backup_cleanup(self, scheduler: AsyncIOScheduler) -> AsyncIOScheduler:
        scheduler.add_job(
            self.cleanup_old_backups,
            trigger=CronTrigger(hour=5, minute=0),
            id="cleanup_old_backups",
            replace_existing=True,
        )
        return scheduler



    async def dump_postgres_db(
        self,
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


    async def backup_database(self,):
        crypto_context = self.crypto_provider.get()
        timestamp = self.dt_formatter.format(datetime.now(UTC))

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            enc_name = f"db_{timestamp}.enc"
            enc_name_secret = f"dump_db:{timestamp}"

            dump_file = tmpdir / f"db_{timestamp}.dump"
            encrypted_file = tmpdir / enc_name

            dek = os.urandom(32)

            encrypted_dek_b64, dek_nonce_b64, dek_sha256_b64 = wrap_dek(
                dek=dek,
                kek=crypto_context.kek
            )

            await self.dump_postgres_db(
                db_name=self.conf.env.db_name,
                db_user=self.conf.env.db_user,
                db_password=self.conf.secrets.db_password,
                db_host=self.conf.env.db_host,
                output_file=dump_file,
            )

            encrypt_file(
                file_path=str(dump_file),
                encrypted_path=str(encrypted_file),
                dek=dek,
            )

            # SHA256 + nonce для файла
            nonce_b64 = extract_nonce_b64(encrypted_file)
            sha256_b64 = calc_sha256_b64(encrypted_file)

            size_bytes = encrypted_file.stat().st_size

            # Сохраняем DEK в storage
            self.secret_storage.create_secret(
                name=enc_name_secret,
                encrypted_data=encrypted_dek_b64,
                nonce=dek_nonce_b64,
                sha256=dek_sha256_b64,
            )

            self.secret_storage.upload_secret_file(
                name=enc_name,
                file_path=encrypted_file,
                nonce_b64=nonce_b64,
                sha256_b64=sha256_b64,
            )

            await self.backup_logs_service.add_backup_log(
                data=CreateBackupLogDTO(
                    storage_file_name=enc_name,
                    storage_encrypted_dek_name=enc_name_secret,
                    encrypted_dek_b64=encrypted_dek_b64,
                    dek_nonce_b64=dek_nonce_b64,
                    size_bytes=size_bytes,
                ),
                make_commit=True
            )


    async def cleanup_old_backups(self, retain_last: int = 2):

        backups = await self.backup_logs_service.get_all_backup_logs_desc()

        if backups is None or len(backups) <= retain_last:
            return

        to_delete = backups[retain_last:]

        for backup in to_delete:
            # удалить файл бэкапа
            try:
                self.secret_storage.purge_secret(backup.storage_file_name)
            except Exception:
                self.logger.exception("Failed to purge backup %s", backup.storage_file_name)

            try:
                # удалить зашифрованный DEK
                self.secret_storage.purge_secret(backup.storage_encrypted_dek_name)
            except Exception:
                self.logger.exception("Failed to purge dek for backup %s", backup.storage_encrypted_dek_name)

            await self.backup_logs_service.delete_backup_log(backup.backup_log_id)
