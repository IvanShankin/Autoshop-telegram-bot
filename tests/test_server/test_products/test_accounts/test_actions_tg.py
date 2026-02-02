import os
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.services.database.categories.models import AccountStorage
from src.services.database.categories.models import AccountServiceType


class TestCheckValidAccounts:
    @pytest.mark.asyncio
    async def test_check_valid_accounts_success(self, monkeypatch, tmp_path):
        from src.services.products.accounts.tg.actions import check_valid_accounts_telethon
        tdata_path = tmp_path / "tdata"
        os.makedirs(tdata_path, exist_ok=True)

        fake_client = AsyncMock()
        fake_client.__aenter__.return_value = fake_client
        fake_client.__aexit__.return_value = None
        fake_client.get_me = AsyncMock(return_value=MagicMock(id=123))

        fake_tdesk = MagicMock()
        fake_tdesk.ToTelethon = AsyncMock(return_value=fake_client)

        from src.services.products.accounts.tg import actions
        monkeypatch.setattr(actions, "TDesktop", lambda path: fake_tdesk)

        res = bool(await check_valid_accounts_telethon(str(tmp_path)))
        assert res is True


    @pytest.mark.asyncio
    async def test_check_valid_accounts_fail(self, monkeypatch, tmp_path):
        from src.services.products.accounts.tg.actions import check_valid_accounts_telethon
        # выкидываем ошибку при инициализации
        from src.services.products.accounts.tg import actions
        monkeypatch.setattr(actions, "TDesktop", lambda path: (_ for _ in ()).throw(Exception("bad")))

        res = bool(await check_valid_accounts_telethon(str(tmp_path)))
        assert res is False



@pytest.mark.asyncio
async def test_check_account_validity_true(tmp_path, monkeypatch):
    """
    Проверяем связку дешифровки и проверки аккаунта: возвращает True.
    """
    from src.services.products.accounts.tg.actions import check_account_validity
    folder_path = tmp_path / "decrypted"
    (folder_path / "tdata").mkdir(parents=True)
    (folder_path / "session.session").write_text("abc")

    # создаём фейковый Telethon клиент
    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get_me(self): return type("User", (), {"id": 1})
        async def connect(self): return True
        async def disconnect(self): return True
        async def is_user_authorized(self): return True

    class FakeTDesktop:
        async def ToTelethon(self, *a, **kw): return FakeClient()

    from src.services.products.accounts.tg import actions
    monkeypatch.setattr(actions, "decryption_tg_account", lambda account, crypto: folder_path)
    monkeypatch.setattr(actions, "TDesktop", lambda path: FakeTDesktop())

    acc = AccountStorage(account_storage_id=5)
    result = await check_account_validity(acc, AccountServiceType.TELEGRAM)
    assert result is True


@pytest.mark.asyncio
async def test_check_account_validity_false(tmp_path, monkeypatch):
    """
    Проверка возвращает False, если Telethon возвращает None.id.
    """
    from src.services.products.accounts.tg.actions import check_account_validity
    folder_path = tmp_path / "decrypted"
    (folder_path / "tdata").mkdir(parents=True)
    (folder_path / "session.session").write_text("abc")

    class FakeClient:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def get_me(self): return type("User", (), {"id": None})

    class FakeTDesktop:
        async def ToTelethon(self, *a, **kw): return FakeClient()

    from src.services.products.accounts.tg import actions
    monkeypatch.setattr(actions, "decryption_tg_account", lambda account, crypto: folder_path)
    monkeypatch.setattr(actions, "TDesktop", lambda path: FakeTDesktop())

    acc = AccountStorage(account_storage_id=6)
    result = await check_account_validity(acc, AccountServiceType.TELEGRAM)
    assert result is False


@pytest.mark.asyncio
async def test_get_auth_codes_reads_codes(tmp_path, monkeypatch):
    """
    Интеграционный тест get_auth_codes — извлекает коды из сообщений.
    """
    from src.services.products.accounts.tg.actions import get_auth_codes
    folder_path = tmp_path / "dec"
    (folder_path / "tdata").mkdir(parents=True)
    (folder_path / "session.session").write_text("abc")

    # подменяем decryption_tg_account, чтобы вернуть нашу папку
    from src.services.products.accounts.tg import actions
    monkeypatch.setattr(actions, "decryption_tg_account", lambda account, crypto: folder_path)

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
