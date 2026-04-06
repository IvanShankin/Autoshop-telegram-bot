import pytest

from src.exceptions.domain import UniversalProductNotFound, UniversalStorageNotFound, UserNotFound
from src.models.create_models.universal import CreateSoldUniversalDTO


class TestUniversalSoldService:

    @pytest.mark.asyncio
    async def test_get_sold_universal_by_owner_id_sets_cache(
        self,
        container_fix,
        create_sold_universal,
    ):
        sold, _ = await create_sold_universal(filling_redis=False)
        items = await container_fix.universal_sold_service.get_sold_universal_by_owner_id(
            owner_id=sold.owner_id,
            language="ru",
        )

        cached = await container_fix.sold_universal_cache_repo.get_by_owner(sold.owner_id, "ru")

        assert items
        assert cached

    @pytest.mark.asyncio
    async def test_get_sold_universal_by_page_returns_items(
        self,
        container_fix,
        create_sold_universal,
    ):
        sold, _ = await create_sold_universal(filling_redis=False)
        page = await container_fix.universal_sold_service.get_sold_universal_by_page(
            user_id=sold.owner_id,
            page=1,
            language="ru",
        )

        assert len(page) >= 1

    @pytest.mark.asyncio
    async def test_get_sold_universal_by_universal_id_populates_cache(
        self,
        container_fix,
        create_sold_universal,
    ):
        _, full = await create_sold_universal(filling_redis=False)
        detail = await container_fix.universal_sold_service.get_sold_universal_by_universal_id(
            sold_universal_id=full.sold_universal_id,
            language="ru",
        )

        cached = await container_fix.sold_universal_single_cache_repo.get(full.sold_universal_id, "ru")

        assert detail is not None
        assert cached is not None

    @pytest.mark.asyncio
    async def test_get_count_sold_universal_returns_value(self, container_fix, create_sold_universal):
        sold, _ = await create_sold_universal(filling_redis=False)
        count = await container_fix.universal_sold_service.get_count_sold_universal(sold.owner_id)

        assert count >= 1

    @pytest.mark.asyncio
    async def test_create_sold_universal_validations(
        self,
        container_fix,
        create_new_user,
        create_universal_storage,
    ):
        user = await create_new_user()
        storage, _ = await create_universal_storage()
        with pytest.raises(UserNotFound):
            await container_fix.universal_sold_service.create_sold_universal(
                CreateSoldUniversalDTO(owner_id=999999, universal_storage_id=storage.universal_storage_id),
                filling_redis=False,
            )

        with pytest.raises(UniversalStorageNotFound):
            await container_fix.universal_sold_service.create_sold_universal(
                CreateSoldUniversalDTO(owner_id=user.user_id, universal_storage_id=999999),
                filling_redis=False,
            )

    @pytest.mark.asyncio
    async def test_create_sold_universal_persists(
        self,
        container_fix,
        create_new_user,
        create_universal_storage,
    ):
        user = await create_new_user()
        storage, _ = await create_universal_storage()
        dto = CreateSoldUniversalDTO(
            owner_id=user.user_id,
            universal_storage_id=storage.universal_storage_id,
        )

        sold = await container_fix.universal_sold_service.create_sold_universal(
            dto,
            filling_redis=False,
        )
        persisted = await container_fix.sold_universal_repo.get_by_id(sold.sold_universal_id)

        assert persisted is not None
        assert persisted.sold_universal_id == sold.sold_universal_id

    @pytest.mark.asyncio
    async def test_delete_sold_universal_removes_record(self, container_fix, create_sold_universal):
        _, full = await create_sold_universal(filling_redis=False)
        await container_fix.universal_sold_service.delete_sold_universal(full.sold_universal_id)

        assert await container_fix.sold_universal_repo.get_by_id(full.sold_universal_id) is None
        assert await container_fix.sold_universal_single_cache_repo.get(full.sold_universal_id, "ru") is None

    @pytest.mark.asyncio
    async def test_delete_sold_universal_not_found(self, container_fix):
        with pytest.raises(UniversalProductNotFound):
            await container_fix.universal_sold_service.delete_sold_universal(999999)
