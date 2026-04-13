import shutil
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import src.application.products.accounts.tg.use_cases.import_use_case as import_use_case_module
import src.application.products.accounts.tg.use_cases.validate as validate_tg_module
import src.application.products.accounts.tg.use_cases.upload as upload_tg_module
from src.application.products.accounts.tg.dto.schemas import BaseAccountProcessingResult
from src.application.products.accounts.tg.use_cases.import_use_case import ImportTelegramAccountsUseCase
from src.application.products.accounts.tg.use_cases.upload import UploadTGAccountsUseCase
from src.application.products.accounts.tg.use_cases.validate import ValidateTgAccount
from src.config import get_config
from src.database.models.categories import AccountServiceType
from src.utils.pars_number import phone_in_e164


def _workspace_dir(name: str) -> Path:
    path = Path(get_config().paths.files_dir.parent) / "_products_tests_tmp" / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class DummyLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class AsyncTelegramClient:
    def __init__(self, result):
        self.result = result

    async def validate(self, *args, **kwargs):
        return self.result


@pytest.mark.asyncio
async def test_validate_tg_account_checks_validity_and_invalid_service(
    container_fix,
    create_category,
    create_product_account,
    monkeypatch,
):
    work_dir = _workspace_dir("validate_tg")
    monkeypatch.setattr(validate_tg_module, "decryption_tg_account", lambda *args, **kwargs: str(work_dir))
    category = await create_category(container_fix, is_product_storage=True)
    _, full = await create_product_account(
        category_id=category.category_id,
        type_account_service=AccountServiceType.TELEGRAM,
        filling_redis=False,
    )

    validator = ValidateTgAccount(
        logger=DummyLogger(),
        tg_client=AsyncTelegramClient(True),
        crypto_provider=container_fix.crypto_provider,
    )

    assert await validator.check_account_validity(
        full,
        AccountServiceType.TELEGRAM,
        full.account_storage.status,
    ) is True

    class WrongService:
        value = "unsupported"

    assert await validator.check_account_validity(
        full,
        WrongService(),
        full.account_storage.status,
    ) is False
    shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_process_single_dir_and_archive(container_fix, monkeypatch):
    fake_user = SimpleNamespace(id=123, phone="+79991110000")
    use_case = ImportTelegramAccountsUseCase(
        account_storage_service=container_fix.account_storage_service,
        account_service=container_fix.account_service,
        account_product_service=container_fix.account_product_service,
        path_builder=container_fix.path_builder,
        tg_client=AsyncTelegramClient(fake_user),
        logger=DummyLogger(),
    )

    work_dir = _workspace_dir("process_tg")
    directory = work_dir / "acc"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "session.session").write_text("session", encoding="utf-8")

    dir_result = await use_case._process_single_dir(str(directory))
    assert dir_result.valid is True
    assert dir_result.user == fake_user
    assert dir_result.phone == fake_user.phone

    archive_path = work_dir / "acc.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("acc/session.session", "session")

    extract_dir = work_dir / "archive_extract"
    extract_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        import_use_case_module,
        "extract_archive_to_temp",
        AsyncMock(return_value=str(extract_dir)),
    )

    archive_result = await use_case._process_single_archive(str(archive_path))
    assert archive_result.valid is True
    assert archive_result.user == fake_user
    assert archive_result.dir_path is not None
    assert Path(archive_result.dir_path).exists()

    shutil.rmtree(Path(archive_result.dir_path), ignore_errors=True)
    shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_split_unique_and_duplicates_filters_duplicates_and_db_values(
    container_fix,
    monkeypatch,
):
    use_case = ImportTelegramAccountsUseCase(
        account_storage_service=container_fix.account_storage_service,
        account_service=container_fix.account_service,
        account_product_service=container_fix.account_product_service,
        path_builder=container_fix.path_builder,
        tg_client=AsyncTelegramClient(True),
        logger=DummyLogger(),
    )

    db_phone = phone_in_e164("+79991110011")
    monkeypatch.setattr(
        container_fix.account_storage_service,
        "get_all_phone_numbers_by_service",
        AsyncMock(return_value=[db_phone]),
    )
    monkeypatch.setattr(
        container_fix.account_storage_service,
        "get_all_tg_ids",
        AsyncMock(return_value=[3]),
    )

    unique_phone = phone_in_e164("+79991110033")
    items = [
        BaseAccountProcessingResult.model_construct(
            valid=True,
            user=SimpleNamespace(id=1, phone="+79991110011"),
            phone="+79991110011",
            dir_path="phone-duplicate",
        ),
        BaseAccountProcessingResult.model_construct(
            valid=True,
            user=SimpleNamespace(id=3, phone="+79991110022"),
            phone="+79991110022",
            dir_path="id-duplicate",
        ),
        BaseAccountProcessingResult.model_construct(
            valid=True,
            user=SimpleNamespace(id=4, phone=unique_phone),
            phone=unique_phone,
            dir_path="unique",
        ),
        BaseAccountProcessingResult.model_construct(
            valid=False,
            user=None,
            phone=None,
            dir_path="invalid",
        ),
    ]

    unique_items, duplicate_items, invalid_items = await use_case._split_unique_and_duplicates(
        items,
        AccountServiceType.TELEGRAM,
    )

    assert [item.dir_path for item in unique_items] == ["unique"]
    assert {item.dir_path for item in duplicate_items} == {"phone-duplicate", "id-duplicate"}
    assert [item.dir_path for item in invalid_items] == ["invalid"]


@pytest.mark.asyncio
async def test_upload_tg_accounts_use_case_yields_archives_and_cleans(
    container_fix,
    create_category,
    create_product_account,
    monkeypatch,
):
    category = await create_category(container_fix, is_product_storage=True)
    for idx in range(5):
        await create_product_account(
            filling_redis=False,
            category_id=category.category_id,
            type_account_service=AccountServiceType.TELEGRAM,
            phone_number=f"+79991110{idx:02d}",
        )

    accounts = await container_fix.account_product_service.get_product_accounts_by_category_id(
        category.category_id,
        get_full=True,
    )

    work_dir = _workspace_dir("upload_tg")
    folders = []
    for idx in range(len(accounts)):
        folder = work_dir / f"folder_{idx}"
        (folder / "tdata").mkdir(parents=True)
        (folder / "session.session").write_text(f"session-{idx}", encoding="utf-8")
        (folder / "tdata" / "info.txt").write_text(f"info-{idx}", encoding="utf-8")
        folders.append(folder)

    def fake_decryption(*args, **kwargs):
        return str(folders.pop(0))

    monkeypatch.setattr(container_fix.account_service, "decryption_tg_account", fake_decryption)
    monkeypatch.setattr(
        upload_tg_module,
        "get_dir_size",
        lambda path: 20 * 1024 * 1024,
    )

    use_case = UploadTGAccountsUseCase(
        conf=container_fix.conf,
        account_service=container_fix.account_service,
        account_product_service=container_fix.account_product_service,
        crypto_provider=container_fix.crypto_provider,
    )

    yielded = []
    async for archive_path in use_case.execute(category.category_id):
        yielded.append(Path(archive_path))
        assert Path(archive_path).exists()

    assert len(yielded) == 3
    for path in yielded:
        assert not path.exists()
    shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_import_tg_accounts_use_case_orchestrates_batches(
    container_fix,
    monkeypatch,
):
    fake_user = SimpleNamespace(id=123, phone="+79991110000")
    use_case = ImportTelegramAccountsUseCase(
        account_storage_service=container_fix.account_storage_service,
        account_service=container_fix.account_service,
        account_product_service=container_fix.account_product_service,
        path_builder=container_fix.path_builder,
        tg_client=AsyncTelegramClient(fake_user),
        logger=DummyLogger(),
    )

    work_dir = _workspace_dir("import_tg")
    input_zip = work_dir / "input.zip"
    with zipfile.ZipFile(input_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("acc/session.session", "session")

    base_dir = work_dir / "base"
    base_dir.mkdir(parents=True, exist_ok=True)

    item = BaseAccountProcessingResult.model_construct(
        valid=True,
        user=fake_user,
        phone=fake_user.phone,
        dir_path="dir",
    )

    monkeypatch.setattr(
        import_use_case_module,
        "extract_archive_to_temp",
        AsyncMock(return_value=str(base_dir)),
    )
    monkeypatch.setattr(
        use_case,
        "_process_archives_batch",
        AsyncMock(return_value=SimpleNamespace(items=[item], total=1)),
    )
    monkeypatch.setattr(
        use_case,
        "_process_dirs_batch",
        AsyncMock(return_value=SimpleNamespace(items=[item], total=1)),
    )
    monkeypatch.setattr(
        use_case,
        "_split_unique_and_duplicates",
        AsyncMock(return_value=([item], [], [])),
    )
    monkeypatch.setattr(
        use_case,
        "_process_inappropriate_acc",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        use_case,
        "_import_in_db",
        AsyncMock(return_value=1),
    )
    monkeypatch.setattr(
        import_use_case_module,
        "archive_if_not_empty",
        AsyncMock(side_effect=["invalid.zip", "duplicate.zip"]),
    )
    monkeypatch.setattr(
        import_use_case_module,
        "cleanup_used_data",
        AsyncMock(return_value=None),
    )

    generator = use_case.import_telegram_accounts_from_archive(
        str(input_zip),
        category_id=1,
        type_account_service=AccountServiceType.TELEGRAM,
    )

    result = await anext(generator)
    assert result.successfully_added == 1
    assert result.total_processed == 2

    assert await anext(generator) is None
    with pytest.raises(StopAsyncIteration):
        await anext(generator)
    shutil.rmtree(work_dir, ignore_errors=True)
