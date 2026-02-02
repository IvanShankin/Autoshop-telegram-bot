import pytest
from src.services.database.categories.models import StorageStatus


@pytest.mark.asyncio
async def test_move_in_account_success(monkeypatch, create_sold_universal):
    from src.services.filesystem.universals_products import move_in_universal, create_path_universal_storage

    _, universal = await create_sold_universal()

    orig_file = create_path_universal_storage(
        status=universal.universal_storage.status,
        uuid=universal.universal_storage.storage_uuid,
        return_path_obj=True
    )
    assert orig_file.exists()

    result = await move_in_universal(universal, StorageStatus.BOUGHT)
    assert result is True

    new_path = create_path_universal_storage(
        status=StorageStatus.BOUGHT,
        uuid=universal.universal_storage.storage_uuid,
        return_path_obj=True
    )
    assert new_path.exists()
    assert not orig_file.exists()