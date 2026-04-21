from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from src.application.models.products.universal.universal_cache_filler_service import UniversalCacheFillerService
from src.database.models.categories.product_universal import (
    SoldUniversal,
    StorageStatus,
    UniversalMediaType,
    UniversalStorage,
)
from src.models.read_models.categories.product_universal import (
    SoldUniversalSmall,
    UniversalStoragePydantic,
)


class TestUniversalCacheFillerService:

    @pytest.mark.asyncio
    async def test_fill_product_universal_by_category_id_sets_cache(
        self,
        container_fix,
        create_product_universal,
    ):
        _, full = await create_product_universal(filling_redis=False)
        await container_fix.universal_cache_filler_service.fill_product_universal_by_category_id(
            full.category_id,
        )

        cached = await container_fix.product_universal_cache_repo.get_by_category(full.category_id)

        assert cached
        assert any(item.product_universal_id == full.product_universal_id for item in cached)

    @pytest.mark.asyncio
    async def test_fill_product_universal_by_product_id_sets_cache(
        self,
        container_fix,
        create_product_universal,
    ):
        _, full = await create_product_universal(filling_redis=False)
        await container_fix.universal_cache_filler_service.fill_product_universal_by_product_id(
            full.product_universal_id,
        )

        cached = await container_fix.product_universal_single_cache_repo.get(full.product_universal_id)

        assert cached is not None

    @pytest.mark.asyncio
    async def test_fill_sold_universal_by_owner_id_sets_cache(
        self,
        container_fix,
        create_sold_universal,
    ):
        sold, _ = await create_sold_universal(filling_redis=False)
        await container_fix.universal_cache_filler_service.fill_sold_universal_by_owner_id(
            sold.owner_id,
        )

        cached = await container_fix.sold_universal_cache_repo.get_by_owner(sold.owner_id, "ru")

        assert cached

    @pytest.mark.asyncio
    async def test_fill_sold_universal_by_universal_id_sets_cache(
        self,
        container_fix,
        create_sold_universal,
    ):
        _, full = await create_sold_universal(filling_redis=False)
        await container_fix.universal_cache_filler_service.fill_sold_universal_by_universal_id(
            full.sold_universal_id,
        )

        cached = await container_fix.sold_universal_single_cache_repo.get(full.sold_universal_id, "ru")

        assert cached is not None

    def test_extract_languages_returns_unique(self):
        item_with_translations = SimpleNamespace(
            storage=SimpleNamespace(translations=[SimpleNamespace(language="ru"), SimpleNamespace(language=None)])
        )
        languages = UniversalCacheFillerService._extract_languages([item_with_translations])

        assert languages == {"ru"}

    def test_from_orm_model_handles_empty_universal_translations(self, create_universal_storage):
        storage = UniversalStorage(
            universal_storage_id=1,
            storage_uuid="storage-uuid",
            original_filename=None,
            encrypted_tg_file_id=None,
            encrypted_tg_file_id_nonce=None,
            checksum="checksum",
            encrypted_key="encrypted-key",
            encrypted_key_nonce="key-nonce",
            key_version=1,
            encryption_algo="AES-GCM-256",
            status=StorageStatus.FOR_SALE,
            media_type=UniversalMediaType.DOCUMENT,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        storage.translations = []

        sold = SoldUniversal(
            sold_universal_id=10,
            owner_id=20,
            universal_storage_id=1,
            sold_at=datetime.now(timezone.utc),
            storage=storage,
        )

        assert UniversalStoragePydantic.from_orm_model(storage, "ru").name == ""
        assert SoldUniversalSmall.from_orm_model(sold, "ru").name == ""
