import csv
import io
import tempfile as pytempfile
import shutil
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from tests.helpers.fixtures.helper_fixture import container_fix
import src.application.products.accounts.generate_exampl_import as generate_exampl_import_module
from src.application.products.accounts.generate_exampl_import import GenerateExamplImportAccount
from src.database.models.categories import AccountServiceType, StorageStatus
from src.domain.crypto.utils import sha256_file
import src.domain.crypto.decrypt as decrypt_module


def _patch_workspace_decrypt_temp(monkeypatch, work_dir: Path):
    original_named_tempfile = pytempfile.NamedTemporaryFile
    original_mkdtemp = pytempfile.mkdtemp

    def named_tempfile(*args, **kwargs):
        kwargs["dir"] = str(work_dir)
        kwargs.setdefault("delete", False)
        return original_named_tempfile(*args, **kwargs)

    def mkdtemp(*args, **kwargs):
        path = work_dir / "extract"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    monkeypatch.setattr(decrypt_module.tempfile, "NamedTemporaryFile", named_tempfile)
    monkeypatch.setattr(decrypt_module.tempfile, "mkdtemp", mkdtemp)


def _patch_workspace_temporary_directory(monkeypatch, work_dir: Path):
    @contextmanager
    def tempdir():
        path = work_dir / "tmp_example"
        path.mkdir(parents=True, exist_ok=True)
        try:
            yield str(path)
        finally:
            shutil.rmtree(path, ignore_errors=True)

    monkeypatch.setattr(generate_exampl_import_module.tempfile, "TemporaryDirectory", tempdir)


@pytest.mark.asyncio
async def test_move_in_account_helper_and_service_move_file(
    container_fix,
    create_account_storage,
):
    helper_account = await create_account_storage(
        status=StorageStatus.FOR_SALE,
        type_account_service=AccountServiceType.TELEGRAM,
    )

    helper_new_path = container_fix.path_builder.build_path_account(
        StorageStatus.BOUGHT,
        helper_account.type_account_service,
        helper_account.storage_uuid,
        as_path=True,
    )
    helper_new_path.parent.mkdir(parents=True, exist_ok=True)

    helper_old_path = container_fix.path_builder.build_path_account(
        helper_account.status,
        helper_account.type_account_service,
        helper_account.storage_uuid,
        as_path=True,
    )
    assert helper_old_path.exists()

    assert await container_fix.account_service.move_in_account(
        helper_account,
        helper_account.type_account_service,
        StorageStatus.BOUGHT,
    ) is True
    assert helper_new_path.exists()
    assert not helper_old_path.exists()

    service_account = await create_account_storage(
        status=StorageStatus.FOR_SALE,
        type_account_service=AccountServiceType.TELEGRAM,
    )
    service_new_path = container_fix.path_builder.build_path_account(
        StorageStatus.BOUGHT,
        service_account.type_account_service,
        service_account.storage_uuid,
        as_path=True,
    )
    service_new_path.parent.mkdir(parents=True, exist_ok=True)

    assert await container_fix.account_service.move_in_account(
        service_account,
        service_account.type_account_service,
        StorageStatus.BOUGHT,
    ) is True
    assert service_new_path.exists()


@pytest.mark.asyncio
async def test_encrypted_tg_account_creates_archive_and_checksum(container_fix):
    work_dir = container_fix.config.paths.temp_dir
    src_dir = work_dir / "src"
    (src_dir / "tdata").mkdir(parents=True)
    (src_dir / "session.session").write_text("session-data", encoding="utf-8")
    (src_dir / "tdata" / "loans.txt").write_text("loans", encoding="utf-8")

    dest = work_dir / "encrypted" / "account.enc"
    result = await container_fix.account_service.encrypted_tg_account(
        str(src_dir),
        str(dest),
    )

    assert result.result is True
    assert Path(result.path_encrypted_acc).exists()
    assert result.checksum == sha256_file(result.path_encrypted_acc)
    shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_decryption_tg_account_extracts_folder(container_fix, create_account_storage, monkeypatch):
    work_dir = container_fix.config.paths.temp_dir
    _patch_workspace_decrypt_temp(monkeypatch, work_dir)
    account_storage = await create_account_storage(
        status=StorageStatus.FOR_SALE,
        type_account_service=AccountServiceType.TELEGRAM,
    )
    crypto = container_fix.crypto_provider.get()

    folder_path = Path(
        container_fix.account_service.decryption_tg_account(
            account_storage,
            crypto,
            account_storage.status,
        )
    )

    assert folder_path.exists()
    assert (folder_path / "session.session").exists()
    assert (folder_path / "tdata").exists()

    shutil.rmtree(folder_path, ignore_errors=True)
    shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_tdata_tg_acc_yields_archive_and_cleans(container_fix, create_account_storage, monkeypatch):
    work_dir = container_fix.config.paths.temp_dir
    _patch_workspace_decrypt_temp(monkeypatch, work_dir)
    account_storage = await create_account_storage(
        status=StorageStatus.FOR_SALE,
        type_account_service=AccountServiceType.TELEGRAM,
    )

    generator = container_fix.account_service.get_tdata_tg_acc(account_storage)
    archive_path = Path(await anext(generator))

    assert archive_path.exists()
    assert zipfile.is_zipfile(archive_path)

    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert not archive_path.exists()
    shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_get_session_tg_acc_yields_session_and_cleans(container_fix, create_account_storage, monkeypatch):
    work_dir = container_fix.config.paths.temp_dir
    _patch_workspace_decrypt_temp(monkeypatch, work_dir)
    account_storage = await create_account_storage(
        status=StorageStatus.FOR_SALE,
        type_account_service=AccountServiceType.TELEGRAM,
    )

    generator = container_fix.account_service.get_session_tg_acc(account_storage)
    session_path = Path(await anext(generator))

    assert session_path.exists()
    assert session_path.name == "session.session"

    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert not session_path.exists()
    shutil.rmtree(work_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_generate_example_import_other_acc_writes_csv(container_fix):
    generator = GenerateExamplImportAccount(container_fix.config)

    generator.generate_example_import_other_acc()
    path = Path(container_fix.config.file_keys.example_csv_for_import_other_acc_key.path)

    assert path.exists()
    rows = list(
        csv.DictReader(
            io.StringIO(path.read_text(encoding="utf-8-sig")),
            delimiter=";",
        )
    )
    assert len(rows) == 3
    assert set(rows[0].keys()) == {"phone", "login", "password"}


@pytest.mark.asyncio
async def test_generate_example_import_tg_acc_writes_zip(container_fix, monkeypatch):
    generator = GenerateExamplImportAccount(container_fix.config)
    work_dir = container_fix.config.paths.temp_dir
    _patch_workspace_temporary_directory(monkeypatch, work_dir)

    assert await generator.generate_example_import_tg_acc() is True
    path = Path(container_fix.config.file_keys.example_zip_for_import_tg_acc_key.path)

    assert path.exists()
    assert zipfile.is_zipfile(path)
    with zipfile.ZipFile(path) as zf:
        assert len(zf.namelist()) > 0
    shutil.rmtree(work_dir, ignore_errors=True)
