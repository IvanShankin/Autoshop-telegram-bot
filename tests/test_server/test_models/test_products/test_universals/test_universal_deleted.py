import pytest

from src.models.create_models.universal import CreateDeletedUniversalDTO


class TestUniversalDeletedService:

    @pytest.mark.asyncio
    async def test_create_deleted_universal_persists(self, container_fix, create_universal_storage):
        storage, _ = await create_universal_storage()
        dto = CreateDeletedUniversalDTO(universal_storage_id=storage.universal_storage_id)

        deleted = await container_fix.universal_deleted_service.create_deleted_universal(dto)
        fetched = await container_fix.deleted_universal_repo.get_by_id(deleted.deleted_universal_id)

        assert deleted.universal_storage_id == storage.universal_storage_id
        assert fetched is not None

    @pytest.mark.asyncio
    async def test_get_deleted_universal_returns_entry(self, container_fix, create_universal_storage):
        storage, _ = await create_universal_storage()
        dto = CreateDeletedUniversalDTO(universal_storage_id=storage.universal_storage_id)
        deleted = await container_fix.universal_deleted_service.create_deleted_universal(dto)

        result = await container_fix.universal_deleted_service.get_deleted_universal(deleted.deleted_universal_id)

        assert result is not None
