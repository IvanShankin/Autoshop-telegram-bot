import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.services.database.selling_accounts.models import AccountStorage, ProductAccounts

# импортируем тестируемые функции
from src.services.filesystem.account_actions import (
    move_file_sync,
    move_file,
    move_in_account,
    rename_sync,
    rename_file,
    create_path_account,
    decryption_tg_account,
    cheek_valid_accounts,
)


def test_move_file_sync_success(tmp_path):
    src = tmp_path / "file.txt"
    dst = tmp_path / "dest" / "file.txt"
    src.write_text("data")

    result = move_file_sync(str(src), str(dst))
    assert result is True
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text() == "data"


def test_move_file_sync_not_found(tmp_path):
    src = tmp_path / "no_file.txt"
    dst = tmp_path / "dest" / "file.txt"
    result = move_file_sync(str(src), str(dst))
    assert result is False


@pytest.mark.asyncio
async def test_move_file_async(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst" / "src.txt"
    src.write_text("abc")

    result = await move_file(str(src), str(dst))
    assert result is True
    assert dst.exists()
    assert dst.read_text() == "abc"


def test_rename_sync_success(tmp_path):
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
    src = tmp_path / "a.txt"
    dst = tmp_path / "b.txt"
    src.write_text("y")

    result = await rename_file(str(src), str(dst))
    assert result is True
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text() == "y"


def test_create_path_account_builds_correct_path(tmp_path, monkeypatch):
    monkeypatch.setattr("src.services.filesystem.account_actions.ACCOUNTS_DIR", tmp_path)
    result = create_path_account("sold", "telegram", "1234")
    expected = tmp_path / "sold" / "telegram" / "1234" / "account.enc"
    assert Path(result) == expected


@pytest.mark.asyncio
async def test_move_in_account_success(tmp_path, monkeypatch):
    # patch ACCOUNTS_DIR
    monkeypatch.setattr("src.services.filesystem.account_actions.ACCOUNTS_DIR", tmp_path)

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

    result = await move_in_account(product, "telegram", "sold")
    assert result is True

    new_path = tmp_path / "sold" / "telegram" / uuid / "account.enc"
    assert new_path.exists()
    assert not orig_file.exists()


@pytest.mark.asyncio
async def test_move_in_account_fail(monkeypatch):
    # имитируем ошибку при move_file
    fake_move = AsyncMock(return_value=False)
    monkeypatch.setattr("src.services.filesystem.account_actions.move_file", fake_move)

    acc_storage = AccountStorage()
    acc_storage.file_path = "fake/file"
    acc_storage.storage_uuid = "uuid"
    acc_storage.account_storage_id = 99
    account = ProductAccounts(account_storage=acc_storage)

    result = await move_in_account(account, "telegram", "sold")
    assert result is False


def test_decryption_tg_account_calls_correct(monkeypatch):
    acc_storage = AccountStorage()
    acc_storage.encrypted_key = "encrypted"
    acc_storage.file_path = "telegram/account.enc"

    fake_master = b"master"
    fake_unwrap = b"key"
    fake_folder = "/tmp/folder"

    monkeypatch.setattr("src.services.filesystem.account_actions.derive_master_key", lambda: fake_master)
    monkeypatch.setattr("src.services.filesystem.account_actions.unwrap_account_key", lambda enc, key: fake_unwrap)
    monkeypatch.setattr("src.services.filesystem.account_actions.decrypt_folder", lambda path, key: fake_folder)
    monkeypatch.setattr("src.services.filesystem.account_actions.ACCOUNTS_DIR", "/root/accounts")

    res = decryption_tg_account(acc_storage)
    assert res == fake_folder


#              cheek_valid_accounts
class TestCheekValidAccounts:
    @pytest.mark.asyncio
    async def test_cheek_valid_accounts_success(self, monkeypatch, tmp_path):
        tdata_path = tmp_path / "tdata"
        os.makedirs(tdata_path, exist_ok=True)

        fake_client = AsyncMock()
        fake_client.__aenter__.return_value = fake_client
        fake_client.__aexit__.return_value = None
        fake_client.get_me = AsyncMock(return_value=MagicMock(id=123))

        fake_tdesk = MagicMock()
        fake_tdesk.ToTelethon = AsyncMock(return_value=fake_client)

        monkeypatch.setattr("src.services.filesystem.account_actions.TDesktop", lambda path: fake_tdesk)

        res = await cheek_valid_accounts(str(tmp_path))
        assert res is True


    @pytest.mark.asyncio
    async def test_cheek_valid_accounts_fail(self, monkeypatch, tmp_path):
        # выкидываем ошибку при инициализации
        monkeypatch.setattr("src.services.filesystem.account_actions.TDesktop", lambda path: (_ for _ in ()).throw(Exception("bad")))

        res = await cheek_valid_accounts(str(tmp_path))
        assert res is False
