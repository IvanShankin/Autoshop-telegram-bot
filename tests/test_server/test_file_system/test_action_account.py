import os
import zipfile

import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from src.services.database.selling_accounts.models import AccountStorage, ProductAccounts
from src.services.secrets import get_crypto_context


# импортируем тестируемые функции


def create_test_directory(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)

    (base / "a.txt").write_text("hello")
    (base / "b.txt").write_text("world")

    sub = base / "nested"
    sub.mkdir()
    (sub / "c.txt").write_text("nested file")

    return base


def test_move_file_sync_success(tmp_path):
    from src.services.filesystem.actions import move_file_sync
    src = tmp_path / "file.txt"
    dst = tmp_path / "dest" / "file.txt"
    src.write_text("data")

    result = move_file_sync(str(src), str(dst))
    assert result is True
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text() == "data"


def test_move_file_sync_not_found(tmp_path):
    from src.services.filesystem.actions import move_file_sync
    src = tmp_path / "no_file.txt"
    dst = tmp_path / "dest" / "file.txt"
    result = move_file_sync(str(src), str(dst))
    assert result is False


@pytest.mark.asyncio
async def test_move_file_async(tmp_path):
    from src.services.filesystem.actions import move_file
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst" / "src.txt"
    src.write_text("abc")

    result = await move_file(str(src), str(dst))
    assert result is True
    assert dst.exists()
    assert dst.read_text() == "abc"


def test_rename_sync_success(tmp_path):
    from src.services.filesystem.account_actions import rename_sync
    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    src.write_text("x")

    result = rename_sync(str(src), str(dst))
    assert result is True
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text() == "x"


@pytest.mark.asyncio
async def test_rename_file_async(tmp_path):
    from src.services.filesystem.account_actions import rename_file
    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    src.write_text("y")

    result = await rename_file(str(src), str(dst))
    assert result is True
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text() == "y"


def test_create_path_account_builds_correct_path(tmp_path, monkeypatch):
    from src.services.filesystem.account_actions import create_path_account
    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions,"ACCOUNTS_DIR", tmp_path)
    result = create_path_account("sold", "telegram", "1234")
    expected = tmp_path / "sold" / "telegram" / "1234" / "account.enc"
    assert Path(result) == expected


@pytest.mark.asyncio
async def test_move_in_account_success(tmp_path, monkeypatch):
    from src.services.filesystem.account_actions import move_in_account
    # patch ACCOUNTS_DIR
    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions, "ACCOUNTS_DIR", tmp_path)

    # создаём src файл
    uuid = "abcd"
    orig_file = tmp_path / "for_sale" / "telegram" / uuid / "account.enc"
    os.makedirs(orig_file.parent, exist_ok=True)
    orig_file.write_text("data")

    # создаём объекты
    acc_storage = AccountStorage()
    acc_storage.file_path = str(Path("for_sale/telegram") / uuid / "account.enc")
    acc_storage.storage_uuid = uuid
    product = ProductAccounts(account_storage=acc_storage)

    result = await move_in_account(product.account_storage, "telegram", "sold")
    assert result is True

    new_path = tmp_path / "sold" / "telegram" / uuid / "account.enc"
    assert new_path.exists()
    assert not orig_file.exists()


@pytest.mark.asyncio
async def test_move_in_account_fail(monkeypatch):
    from src.services.filesystem.account_actions import move_in_account
    # имитируем ошибку при move_file
    fake_move = AsyncMock(return_value=False)
    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions, "move_file", fake_move)

    acc_storage = AccountStorage()
    acc_storage.file_path = "fake/file"
    acc_storage.storage_uuid = "uuid"
    acc_storage.account_storage_id = 99
    account = ProductAccounts(account_storage=acc_storage)

    result = await move_in_account(account.account_storage, "telegram", "sold")
    assert result is False


async def test_decryption_tg_account_calls_correct(monkeypatch, create_account_storage):
    from src.services.filesystem.account_actions import decryption_tg_account
    from src.services.filesystem import account_actions

    crypto = get_crypto_context()
    acc_storage = await create_account_storage()
    fake_folder = "/tmp/folder"

    monkeypatch.setattr(account_actions, "decrypt_folder", lambda path, key: fake_folder)
    monkeypatch.setattr(account_actions, "ACCOUNTS_DIR", "/root/accounts")

    res = decryption_tg_account(acc_storage, crypto)
    assert res == fake_folder


@pytest.mark.asyncio
async def test_encrypt_decrypt_directory_roundtrip(
    tmp_path,
    monkeypatch,
):
    """
    Полный round-trip:
    directory -> encrypt -> decrypt -> directory
    """
    from src.services.filesystem.input_account import encrypted_tg_account
    from src.services.filesystem.account_actions import decryption_tg_account

    # Исходная директория
    src_dir = create_test_directory(tmp_path / "src")

    # Путь к зашифрованному архиву
    encrypted_file = tmp_path / "encrypted" / "account.enc"

    # Подменяем ACCOUNTS_DIR
    import src.services.filesystem.account_actions as fs_module
    monkeypatch.setattr(fs_module, "ACCOUNTS_DIR", tmp_path)


    enc = await encrypted_tg_account(
        src_directory=str(src_dir),
        dest_encrypted_path=str(encrypted_file),
    )

    assert enc.result is True
    assert encrypted_file.exists()

    storage = AccountStorage(
        encrypted_key=enc.encrypted_key_b64,
        encrypted_key_nonce=enc.encrypted_key_nonce,
        file_path=encrypted_file.relative_to(tmp_path).as_posix(),
    )

    crypto = get_crypto_context()
    decrypted_dir = decryption_tg_account(
        account_storage=storage,
        crypto=crypto,
    )

    decrypted_dir = Path(decrypted_dir)

    assert (decrypted_dir / "a.txt").read_text() == "hello"
    assert (decrypted_dir / "b.txt").read_text() == "world"
    assert (decrypted_dir / "nested" / "c.txt").read_text() == "nested file"


@pytest.mark.asyncio
async def test_get_tdata_tg_acc_creates_archive(tmp_path, monkeypatch):
    """
    Интеграционный тест: функция должна создать zip архив из tdata.
    """
    from src.services.filesystem.account_actions import get_tdata_tg_acc
    # создаём фейковую структуру папки, будто она "расшифрована"
    folder_path = tmp_path / "decrypted"
    tdata_dir = folder_path / "tdata"
    tdata_dir.mkdir(parents=True)
    (tdata_dir / "data.txt").write_text("hello")

    # переопределяем decryption_tg_account, чтобы вернуть этот путь
    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions, "decryption_tg_account", lambda account, kek: folder_path)

    # создаём объект AccountStorage
    acc = AccountStorage(account_storage_id=1)

    gen = get_tdata_tg_acc(acc)
    archive_path = await anext(gen)

    # проверяем, что zip файл реально создан и содержит data.txt
    assert archive_path
    assert Path(archive_path).exists()
    with zipfile.ZipFile(archive_path, "r") as zf:
        path_result = Path("tdata") / "data.txt"
        result = False
        for path in zf.namelist():
            if path_result == Path(path):
                result = True

        assert result


@pytest.mark.asyncio
async def test_get_tdata_tg_acc_handles_missing_tdata(tmp_path, monkeypatch):
    """
    Если папки tdata нет — должно вернуть False.
    """
    from src.services.filesystem.account_actions import get_tdata_tg_acc
    folder_path = tmp_path / "decrypted"
    folder_path.mkdir()

    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions, "decryption_tg_account", lambda account, kek: folder_path)

    acc = AccountStorage(account_storage_id=2)

    gen = get_tdata_tg_acc(acc)
    res = await anext(gen)
    assert res is False


@pytest.mark.asyncio
async def test_get_session_tg_acc_reads_existing_file(tmp_path, monkeypatch):
    """
    Проверяем, что get_session_tg_acc возвращает путь к session.session.
    """
    from src.services.filesystem.account_actions import get_session_tg_acc
    folder_path = tmp_path / "decrypted"
    folder_path.mkdir()
    (folder_path / "session.session").write_text("data")

    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions, "decryption_tg_account", lambda account, kek: folder_path)

    acc = AccountStorage(account_storage_id=3)
    gen = get_session_tg_acc(acc)
    path = await anext(gen)

    assert os.path.isfile(path)
    assert path.endswith("session.session")


@pytest.mark.asyncio
async def test_get_session_tg_acc_missing_file(tmp_path, monkeypatch):
    """
    Если session.session отсутствует — возвращает False.
    """
    from src.services.filesystem.account_actions import get_session_tg_acc
    folder_path = tmp_path / "decrypted"
    folder_path.mkdir()

    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions, "decryption_tg_account", lambda account, kek: folder_path)

    acc = AccountStorage(account_storage_id=4)
    gen = get_session_tg_acc(acc)
    res = await anext(gen)
    assert res is False

