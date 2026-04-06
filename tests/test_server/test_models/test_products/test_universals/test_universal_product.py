import pytest

from src.exceptions.domain import CategoryNotFound, UniversalProductNotFound, UniversalStorageNotFound
from src.models.create_models.universal import CreateProductUniversalDTO


class TestUniversalProductService:

    @pytest.mark.asyncio
    async def test_get_product_universal_by_category_id_returns_items(
        self,
        container_fix,
        create_product_universal,
    ):
        _, full = await create_product_universal()
        result = await container_fix.universal_product_service.get_product_universal_by_category_id(
            category_id=full.category_id,
            language="ru",
            get_full=True,
        )

        assert result
        assert any(item.product_universal_id == full.product_universal_id for item in result)

    @pytest.mark.asyncio
    async def test_get_product_universal_by_product_id_populates_cache(
        self,
        container_fix,
        create_product_universal,
    ):
        _, full = await create_product_universal()

        detail = await container_fix.universal_product_service.get_product_universal_by_product_id(
            full.product_universal_id,
        )

        cached = await container_fix.product_universal_single_cache_repo.get(full.product_universal_id)

        assert detail is not None
        assert cached is not None

    @pytest.mark.asyncio
    async def test_create_product_universal_requires_existing_storage_and_category(
        self,
        container_fix,
        create_category,
        create_universal_storage,
    ):
        category = await create_category()
        with pytest.raises(UniversalStorageNotFound):
            await container_fix.universal_product_service.create_product_universal(
                CreateProductUniversalDTO(universal_storage_id=999999, category_id=category.category_id),
                filling_redis=False,
            )

        storage, _ = await create_universal_storage()
        with pytest.raises(CategoryNotFound):
            await container_fix.universal_product_service.create_product_universal(
                CreateProductUniversalDTO(universal_storage_id=storage.universal_storage_id, category_id=999999),
                filling_redis=False,
            )

    @pytest.mark.asyncio
    async def test_create_product_universal_persists(self, container_fix, create_category, create_universal_storage):
        category = await create_category()
        storage, _ = await create_universal_storage()
        dto = CreateProductUniversalDTO(
            universal_storage_id=storage.universal_storage_id,
            category_id=category.category_id,
        )

        created = await container_fix.universal_product_service.create_product_universal(
            dto,
            filling_redis=False,
        )
        fetched = await container_fix.product_universal_repo.get_by_id(created.product_universal_id)

        assert fetched is not None
        assert fetched.product_universal_id == created.product_universal_id

    @pytest.mark.asyncio
    async def test_delete_product_universal_removes_record_and_cache(
        self,
        container_fix,
        create_product_universal,
    ):
        _, full = await create_product_universal()

        await container_fix.universal_product_service.delete_product_universal(full.product_universal_id)

        assert await container_fix.product_universal_repo.get_by_id(full.product_universal_id) is None
        assert await container_fix.product_universal_single_cache_repo.get(full.product_universal_id) is None

    @pytest.mark.asyncio
    async def test_delete_product_universal_not_found(
        self,
        container_fix,
    ):
        with pytest.raises(UniversalProductNotFound):
            await container_fix.universal_product_service.delete_product_universal(999999)

    @pytest.mark.asyncio
    async def test_delete_product_universal_by_category_cleans_storage_and_cache(
        self,
        container_fix,
        create_product_universal,
    ):
        _, full = await create_product_universal()
        await container_fix.universal_product_service.delete_product_universal_by_category(full.category_id)

        assert await container_fix.product_universal_repo.get_by_id(full.product_universal_id) is None
        assert await container_fix.universal_storage_repo.get_by_id(
            full.universal_storage.universal_storage_id
        ) is None
        assert await container_fix.product_universal_cache_repo.get_by_category(full.category_id) == []
