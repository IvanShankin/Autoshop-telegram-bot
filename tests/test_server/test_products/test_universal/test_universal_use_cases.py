import shutil
import zipfile
import tempfile as pytempfile
import pytest
from pathlib import Path

from sqlalchemy import select

from src.database.models.categories import StorageStatus, UniversalMediaType
from src.database.models.categories.product_universal import ProductUniversal
import src.infrastructure.files.file_system as file_system_module


@pytest.mark.asyncio
async def test_move_universal_storage_moves_file_and_returns_path(
    container_fix,
    create_category,
    create_product_universal,
):
    category = await create_category(container_fix, is_product_storage=True)
    _, full = await create_product_universal(category_id=category.category_id)

    old_path = container_fix.path_builder.build_path_universal_storage(
        full.universal_storage.status,
        full.universal_storage.storage_uuid,
        as_path=True,
    )

    new_path = await container_fix.universal_product.move_universal_storage(
        full.universal_storage,
        StorageStatus.BOUGHT,
    )

    assert new_path
    assert Path(new_path).exists()
    assert not old_path.exists()


@pytest.mark.asyncio
async def test_validations_universal_product_checks_valid_and_invalid_path(
    container_fix,
    create_category,
    create_product_universal,
):
    category = await create_category(container_fix, is_product_storage=True)
    _, full = await create_product_universal(category_id=category.category_id)

    assert await container_fix.validations_universal_products.check_valid_universal_product(
        full,
        full.universal_storage.status,
    ) is True

    container_fix.validations_universal_products.path_builder.build_path_universal_storage = lambda *args, **kwargs: "missing_file/file.enc"

    assert await container_fix.validations_universal_products.check_valid_universal_product(
        full,
        full.universal_storage.status,
    ) is False


@pytest.mark.asyncio
async def test_generate_example_universal_import_zip(container_fix):
    generator = container_fix.generate_exampl_universal_product_import

    path = generator.generate()

    assert path.exists()
    assert zipfile.is_zipfile(path)

    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        assert "manifest.csv" in names
        assert "files/file_001.pdf" in names
        assert "files/file_002.pdf" in names


@pytest.mark.asyncio
async def test_upload_universal_products_exports_zip_and_cleans(
    container_fix,
    create_category,
    create_product_universal,
):
    category = await create_category(container_fix, is_product_storage=True)
    await create_product_universal(category_id=category.category_id)

    use_case = container_fix.upload_universal_products_use_case

    generator = use_case.execute(category)
    archive_path = Path(await anext(generator))

    assert archive_path.exists()
    assert zipfile.is_zipfile(archive_path)

    with zipfile.ZipFile(archive_path) as zf:
        names = set(zf.namelist())
        assert "manifest.csv" in names
        assert any(name.startswith("files/") for name in names)

    assert await anext(generator) is None
    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert not archive_path.exists()


@pytest.mark.asyncio
async def test_import_universal_products_imports_generated_archive(
    container_fix,
    create_category,
    session_db_fix,
):
    work_dir = container_fix.config.paths.temp_dir
    category = await create_category(container_fix, is_product_storage=True)
    archive_source = container_fix.generate_exampl_universal_product_import.generate()
    archive_path = work_dir / archive_source.name
    shutil.copy2(archive_source, archive_path)

    original_mkdtemp = pytempfile.mkdtemp

    def workspace_mkdtemp(*args, **kwargs):
        path = work_dir / "extract"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    file_system_module.tempfile.mkdtemp = workspace_mkdtemp

    use_case = container_fix.import_universal_product_use_case

    added = await use_case.execute(
        archive_path,
        UniversalMediaType.MIXED,
        category.category_id,
    )

    assert added == 2

    db_result = await session_db_fix.execute(
        select(ProductUniversal).where(ProductUniversal.category_id == category.category_id)
    )
    assert len(db_result.scalars().all()) == 2
    file_system_module.tempfile.mkdtemp = original_mkdtemp
    shutil.rmtree(work_dir, ignore_errors=True)
