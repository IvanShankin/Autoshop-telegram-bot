import csv
import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.application.products.accounts.other.dto import REQUIRED_HEADERS
from src.application.products.accounts.other.use_cases.import_use_case import ImportOtherAccountsUseCase
from src.application.products.accounts.other.use_cases.upload import UploadOtherAccountsUseCase
from src.database.models.categories import AccountServiceType
from src.database.models.categories.product_account import ProductAccounts
from src.infrastructure.files.file_system import make_csv_bytes
from src.config import get_config
from src.application.products.accounts.other.use_cases import validate as validate_other_module


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class DummyEventHandler:
    async def send_log(self, *args, **kwargs):
        return None


def _workspace_dir(name: str) -> Path:
    path = Path(get_config().paths.files_dir.parent) / "_products_tests_tmp" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.mark.asyncio
async def test_validate_other_accounts_use_case_checks_validity(
    container_fix,
    create_category,
    create_product_account,
):
    category = await create_category(container_fix, is_product_storage=True)
    _, full = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
        filling_redis=False,
    )

    assert await container_fix.validate_other_account.check_valid(full) is True
    assert await container_fix.validate_other_account.check_valid(
        full.model_copy(update={"account_storage": SimpleNamespace(encrypted_key="broken")})
    ) is False


@pytest.mark.asyncio
async def test_upload_other_accounts_use_case_exports_csv(
    container_fix,
    create_category,
    create_product_account,
):
    category = await create_category(container_fix, is_product_storage=True)
    await create_product_account(
        filling_redis=False,
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
        phone_number="+79991110001",
    )
    await create_product_account(
        filling_redis=False,
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
        phone_number="+79991110002",
    )

    accounts = await container_fix.account_product_service.get_product_accounts_by_category_id(
        category.category_id,
        get_full=True,
    )

    class StubStorageService:
        def __init__(self, values):
            self.values = values

        async def get_account_storage_by_category(self, category_id: int):
            return self.values

    use_case = UploadOtherAccountsUseCase(
        crypto_provider=container_fix.crypto_provider,
        publish_event_handler=DummyEventHandler(),
        account_storage_service=StubStorageService(accounts),
        logger=DummyLogger(),
    )

    csv_bytes = await use_case.execute(category.category_id)
    rows = list(
        csv.DictReader(
            io.StringIO(csv_bytes.decode("utf-8-sig")),
            delimiter=";",
        )
    )

    assert len(rows) == 2
    assert {row["login"] for row in rows} == {"login_encrypted"}
    assert {row["password"] for row in rows} == {"password_encrypted"}


@pytest.mark.asyncio
async def test_import_other_accounts_use_case_imports_rows(
    container_fix,
    create_category,
    session_db_fix,
):
    category = await create_category(container_fix, is_product_storage=True)
    csv_stream = io.BytesIO(
        make_csv_bytes(
            [
                {"phone": "+79991110011", "login": "login-1", "password": "pass-1"},
                {"phone": "+79991110012", "login": "login-2", "password": "pass-2"},
            ],
            REQUIRED_HEADERS,
        )
    )

    use_case = ImportOtherAccountsUseCase(
        crypto_provider=container_fix.crypto_provider,
        publish_event_handler=DummyEventHandler(),
        account_product_service=container_fix.account_product_service,
        account_storage_service=container_fix.account_storage_service,
        logger=DummyLogger(),
    )

    result = await use_case.execute(
        csv_stream,
        category.category_id,
        AccountServiceType.OTHER,
    )

    assert result.successfully_added == 2
    assert result.total_processed == 2
    assert result.errors_csv_bytes is None

    db_result = await session_db_fix.execute(
        select(ProductAccounts).where(ProductAccounts.category_id == category.category_id)
    )
    assert len(db_result.scalars().all()) == 2


@pytest.mark.asyncio
async def test_validate_other_accounts_use_case_false_on_unwrap_error(
    container_fix,
    create_category,
    create_product_account,
    monkeypatch,
):
    category = await create_category(container_fix, is_product_storage=True)
    _, full = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.OTHER,
        filling_redis=False,
    )
    monkeypatch.setattr(
        validate_other_module,
        "unwrap_dek",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad")),
    )

    assert await container_fix.validate_other_account.check_valid(full) is False
