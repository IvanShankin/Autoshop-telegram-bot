import os
import zipfile
from datetime import datetime, timezone

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.services.database.selling_accounts.models import AccountStorage, ProductAccounts

# импортируем тестируемые функции



def test_move_file_sync_success(tmp_path):
    from src.services.filesystem.account_actions import move_file_sync
    src = tmp_path / "file.txt"
    dst = tmp_path / "dest" / "file.txt"
    src.write_text("data")

    result = move_file_sync(str(src), str(dst))
    assert result is True
    assert not src.exists()
    assert dst.exists()
    assert dst.read_text() == "data"


def test_move_file_sync_not_found(tmp_path):
    from src.services.filesystem.account_actions import move_file_sync
    src = tmp_path / "no_file.txt"
    dst = tmp_path / "dest" / "file.txt"
    result = move_file_sync(str(src), str(dst))
    assert result is False


@pytest.mark.asyncio
async def test_move_file_async(tmp_path):
    from src.services.filesystem.account_actions import move_file
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
    monkeypatch.setattr("src.services.filesystem.account_actions.ACCOUNTS_DIR", tmp_path)
    result = create_path_account("sold", "telegram", "1234")
    expected = tmp_path / "sold" / "telegram" / "1234" / "account.enc"
    assert Path(result) == expected


@pytest.mark.asyncio
async def test_move_in_account_success(tmp_path, monkeypatch):
    from src.services.filesystem.account_actions import move_in_account
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
    monkeypatch.setattr("src.services.filesystem.account_actions.move_file", fake_move)

    acc_storage = AccountStorage()
    acc_storage.file_path = "fake/file"
    acc_storage.storage_uuid = "uuid"
    acc_storage.account_storage_id = 99
    account = ProductAccounts(account_storage=acc_storage)

    result = await move_in_account(account.account_storage, "telegram", "sold")
    assert result is False


def test_decryption_tg_account_calls_correct(monkeypatch):
    from src.services.filesystem.account_actions import _decryption_tg_account
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

    res = _decryption_tg_account(acc_storage)
    assert res == fake_folder


class TestCheckValidAccounts:
    @pytest.mark.asyncio
    async def test_check_valid_accounts_success(self, monkeypatch, tmp_path):
        from src.services.tg_accounts.actions import _check_valid_accounts_telethon
        tdata_path = tmp_path / "tdata"
        os.makedirs(tdata_path, exist_ok=True)

        fake_client = AsyncMock()
        fake_client.__aenter__.return_value = fake_client
        fake_client.__aexit__.return_value = None
        fake_client.get_me = AsyncMock(return_value=MagicMock(id=123))

        fake_tdesk = MagicMock()
        fake_tdesk.ToTelethon = AsyncMock(return_value=fake_client)

        monkeypatch.setattr("src.services.tg_accounts.actions.TDesktop", lambda path: fake_tdesk)

        res = await _check_valid_accounts_telethon(str(tmp_path))
        assert res is True


    @pytest.mark.asyncio
    async def test_check_valid_accounts_fail(self, monkeypatch, tmp_path):
        from src.services.tg_accounts.actions import _check_valid_accounts_telethon
        # выкидываем ошибку при инициализации
        monkeypatch.setattr("src.services.tg_accounts.actions.TDesktop", lambda path: (_ for _ in ()).throw(Exception("bad")))

        res = await _check_valid_accounts_telethon(str(tmp_path))
        assert res is False


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

    # переопределяем _decryption_tg_account, чтобы вернуть этот путь
    from src.services.filesystem import account_actions
    monkeypatch.setattr(account_actions, "_decryption_tg_account", lambda a: folder_path)

    # создаём объект AccountStorage
    acc = AccountStorage(account_storage_id=1)

    gen = get_tdata_tg_acc(acc)
    archive_path = await anext(gen)

    # проверяем, что zip файл реально создан и содержит data.txt
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
    monkeypatch.setattr(account_actions, "_decryption_tg_account", lambda a: folder_path)

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
    monkeypatch.setattr(account_actions, "_decryption_tg_account", lambda a: folder_path)

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
    monkeypatch.setattr(account_actions, "_decryption_tg_account", lambda a: folder_path)

    acc = AccountStorage(account_storage_id=4)
    gen = get_session_tg_acc(acc)
    res = await anext(gen)
    assert res is False


@pytest.mark.asyncio
async def test_check_account_validity_true(tmp_path, monkeypatch):
    """
    Проверяем связку дешифровки и проверки аккаунта: возвращает True.
    """
    from src.services.tg_accounts.actions import check_account_validity
    folder_path = tmp_path / "decrypted"
    (folder_path / "tdata").mkdir(parents=True)
    (folder_path / "session.session").write_text("abc")

    # создаём фейковый Telethon клиент
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get_me(self): return type("User", (), {"id": 1})

    class FakeTDesktop:
        async def ToTelethon(self, *a, **kw): return FakeClient()

    from src.services.tg_accounts import actions
    monkeypatch.setattr(actions, "_decryption_tg_account", lambda a: folder_path)
    monkeypatch.setattr(actions, "TDesktop", lambda path: FakeTDesktop())
    monkeypatch.setattr(actions, "TYPE_ACCOUNT_SERVICES", ["telegram"])

    acc = AccountStorage(account_storage_id=5)
    result = await check_account_validity(acc, "telegram")
    assert result is True


@pytest.mark.asyncio
async def test_check_account_validity_false(tmp_path, monkeypatch):
    """
    Проверка возвращает False, если Telethon возвращает None.id.
    """
    from src.services.tg_accounts.actions import check_account_validity
    folder_path = tmp_path / "decrypted"
    (folder_path / "tdata").mkdir(parents=True)
    (folder_path / "session.session").write_text("abc")

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get_me(self): return type("User", (), {"id": None})

    class FakeTDesktop:
        async def ToTelethon(self, *a, **kw): return FakeClient()

    from src.services.tg_accounts import actions
    monkeypatch.setattr(actions, "_decryption_tg_account", lambda a: folder_path)
    monkeypatch.setattr(actions, "TDesktop", lambda path: FakeTDesktop())
    monkeypatch.setattr(actions, "TYPE_ACCOUNT_SERVICES", ["telegram"])

    acc = AccountStorage(account_storage_id=6)
    result = await check_account_validity(acc, "telegram")
    assert result is False


@pytest.mark.asyncio
async def test_get_auth_codes_reads_codes(tmp_path, monkeypatch):
    """
    Интеграционный тест get_auth_codes — извлекает коды из сообщений.
    """
    from src.services.tg_accounts.actions import get_auth_codes
    folder_path = tmp_path / "dec"
    (folder_path / "tdata").mkdir(parents=True)
    (folder_path / "session.session").write_text("abc")

    # подменяем _decryption_tg_account, чтобы вернуть нашу папку
    from src.services.tg_accounts import actions
    monkeypatch.setattr(actions, "_decryption_tg_account", lambda a: folder_path)

    fake_msg1 = type("Msg", (), {"message": "Your code: 12345", "date": datetime.now(timezone.utc)})
    fake_msg2 = type("Msg", (), {"message": "Code 67890!", "date": datetime.now(timezone.utc)})

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get_messages(self, *a, **kw): return [fake_msg1, fake_msg2]

    class FakeTDesktop:
        async def ToTelethon(self, *a, **kw): return FakeClient()

    monkeypatch.setattr(actions, "TDesktop", lambda p: FakeTDesktop())

    acc = AccountStorage(account_storage_id=7)
    result = await get_auth_codes(acc)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(code, str) for _, code in result)
