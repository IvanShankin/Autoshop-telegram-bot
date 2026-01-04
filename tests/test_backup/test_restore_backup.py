import base64
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from src.services.secrets import encrypt_bytes
from src.tools import restore_backup
from src.tools.restore_backup import restore_postgres



@patch("subprocess.run")
def test_restore_postgres(mock_run):
    class DummyConfig:
        class env:
            db_user = "user"
            db_host = "host"
            db_name = "db"
        class secrets:
            db_password = "pass"

    dummy_file = Path("/tmp/fake.dump")
    restore_postgres(dummy_file, DummyConfig)
    mock_run.assert_called_once()
    # Проверим, что вызывается pg_restore
    assert "pg_restore" in mock_run.call_args[0][0][0]



@pytest.mark.asyncio
async def test_main_real_crypto(monkeypatch):
    # Аргументы
    monkeypatch.setattr("sys.argv", [
        "restore_backup.py",
        "--secret-srt-dek-name", "backup1",
        "--secret-file-name", "file_name1",
        "--env", "DEV",
        "--dry-run"
    ])

    # confirm_destruction
    monkeypatch.setattr(restore_backup, "confirm_destruction", lambda env, force: None)

    # KEK и DEK
    fake_kek = os.urandom(32)
    dek_bytes = os.urandom(32)
    monkeypatch.setattr(restore_backup, "get_kek", lambda: fake_kek)

    # Шифруем DEK настоящим KEK
    encrypted_dek_bytes = encrypt_bytes(dek_bytes, fake_kek)
    nonce = encrypted_dek_bytes[:12]
    encrypted_data_b64 = base64.b64encode(encrypted_dek_bytes[12:]).decode()
    nonce_b64 = base64.b64encode(nonce).decode()

    # Мок storage
    mock_storage = MagicMock()
    mock_storage.get_secret_string.return_value = {
        "encrypted_data": encrypted_data_b64,
        "nonce": nonce_b64,
        "storage_object_name": "file.enc"
    }

    def fake_download_secret_file(name, dst_path):
        # записываем зашифрованные данные для decrypt_bytes
        ciphertext = encrypt_bytes(b"PLAINTEXT DATA", dek_bytes)
        dst_path.write_bytes(ciphertext)

    mock_storage.download_secret_file.side_effect = fake_download_secret_file
    monkeypatch.setattr(restore_backup, "get_storage_client", lambda: mock_storage)

    # Мок restore_postgres
    monkeypatch.setattr(restore_backup, "restore_postgres", lambda dump_file, config: None)

    # Выполняем main
    await restore_backup.main()

    # Проверяем вызовы
    mock_storage.download_secret_file.assert_called_once()
    mock_storage.get_secret_string.assert_called_once_with("backup1")