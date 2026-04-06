import pytest

from src.database.models.categories import StorageStatus


class TestAccountsCacheFillerService:

    @pytest.mark.asyncio
    async def test_fill_product_accounts_by_category_populates_cache(
        self,
        container_fix,
        create_product_account,
    ):
        product, _ = await create_product_account()

        await container_fix.accounts_cache_filler_service.fill_product_accounts_by_category_id(product.category_id)

        cached = await container_fix.accounts_cache_repo.get_product_accounts_by_category(product.category_id)
        assert cached

    @pytest.mark.asyncio
    async def test_fill_product_account_by_account_id_cleans_if_not_for_sale(
        self,
        container_fix,
        create_product_account,
        session_db_fix,
    ):
        product, full = await create_product_account(status = StorageStatus.BOUGHT)

        await container_fix.accounts_cache_filler_service.fill_product_account_by_account_id(product.account_id)
        assert not await container_fix.accounts_cache_repo.get_product_account_by_account_id(product.account_id)

    @pytest.mark.asyncio
    async def test_fill_product_account_by_account_id_sets_when_available(
        self,
        container_fix,
        create_product_account,
    ):
        product, _ = await create_product_account()

        await container_fix.accounts_cache_filler_service.fill_product_account_by_account_id(product.account_id)
        assert await container_fix.accounts_cache_repo.get_product_account_by_account_id(product.account_id)

    @pytest.mark.asyncio
    async def test_fill_sold_accounts_by_owner_id_sets_entries(
        self,
        container_fix,
        create_sold_account,
    ):
        sold, _ = await create_sold_account()
        await container_fix.accounts_cache_filler_service.fill_sold_accounts_by_owner_id(sold.owner_id)

        result = await container_fix.accounts_cache_repo.get_sold_accounts_by_owner_id(sold.owner_id, "ru")
        assert result

    @pytest.mark.asyncio
    async def test_fill_sold_accounts_by_account_id_sets_entries(
        self,
        container_fix,
        create_sold_account,
    ):
        sold, _ = await create_sold_account()
        await container_fix.accounts_cache_filler_service.fill_sold_accounts_by_account_id(sold.sold_account_id)

        cached = await container_fix.accounts_cache_repo.get_sold_accounts_by_account_id(sold.sold_account_id, "ru")
        assert cached is not None
