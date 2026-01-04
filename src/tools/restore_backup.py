import argparse
import asyncio
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from getpass import getpass

from src.config import init_env, get_config
from src.services.secrets import decrypt_bytes, unwrap_dek, derive_kek
from src.services.secrets.loader import get_storage_client


def parse_args():
    parser = argparse.ArgumentParser("Restore PostgreSQL backup")
    parser.add_argument("--secret-srt-dek-name", required=True)
    parser.add_argument("--secret-file-name", required=True)
    parser.add_argument("--env", required=True, choices=["DEV", "PROD", "TEST"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def confirm_destruction(env: str, force: bool):
    if force:
        return

    print(f"\nWARNING: This will DESTROY {env} database.")
    phrase = f"RESTORE {env} DATABASE"

    typed = input(f'Type "{phrase}" to continue: ')
    if typed != phrase:
        print("Aborted.")
        sys.exit(1)


def get_kek() -> bytes:
    passphrase = getpass("Enter master passphrase: ")
    kek = derive_kek(passphrase)
    del passphrase
    return kek


def restore_postgres(dump_file: Path, config):
    print("Restoring PostgreSQL database...")

    subprocess.run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--dbname",
            f"postgresql://{config.env.db_user}:{config.secrets.db_password}"
            f"@{config.env.db_host}/{config.env.db_name}",
            str(dump_file),
        ],
        check=True,
    )

    print("Database restored successfully.")


async def main():
    """Возьмёт бэкап БД с сервиса хранения и установит его"""
    args = parse_args()
    init_env()

    config = get_config()
    confirm_destruction(args.env, args.force)

    kek = get_kek()
    storage = get_storage_client()

    enc_dek = storage.get_secret_string(args.secret_srt_dek_name) # берём с сервиса хранения DEK

    # расшифровка DEK
    dek = unwrap_dek(
        encrypted_data_b64=enc_dek["encrypted_data"],
        nonce_b64=enc_dek["nonce"],
        kek=kek,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        enc_file = tmpdir / "backup.enc"
        dump_file = tmpdir / "backup.dump"

        # скачать файл
        storage.download_secret_file(
            name=args.secret_file_name,
            dst_path=enc_file,
        )

        # расшифровать
        plaintext = decrypt_bytes(enc_file.read_bytes(), dek)
        dump_file.write_bytes(plaintext)

        if args.dry_run:
            print("Dry-run successful.")
            return

        restore_postgres(dump_file, config)

        enc_file.unlink(missing_ok=True)
        dump_file.unlink(missing_ok=True)


if __name__ == '__main__':
    asyncio.run(main())
