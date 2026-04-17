import pytest
from sqlalchemy import select

from src.database.models.categories.product_account import ProductAccounts, StorageStatus
from src.exceptions import TheCategoryNotStorageAccount
from src.exceptions.domain import CategoryNotFound, ProductAccountNotFound
from src.models.create_models.accounts import CreateProductAccountDTO
from src.models.read_models import ProductAccountFull


class TestAccountProductService:

    @pytest.mark.asyncio
    async def test_get_product_accounts_by_category_id_uses_cache(
        self,
        container_fix,
        create_product_account,
    ):
        product, _ = await create_product_account()

        result = await container_fix.account_product_service.get_product_accounts_by_category_id(
            product.category_id
        )
        assert result
        assert any(item.account_id == product.account_id for item in result)

        cached = await container_fix.accounts_cache_repo.get_product_accounts_by_category(product.category_id)
        assert cached

        full_result = await container_fix.account_product_service.get_product_accounts_by_category_id(
            product.category_id,
            get_full=True,
        )
        assert isinstance(full_result[0], ProductAccountFull)

    @pytest.mark.asyncio
    async def test_get_product_account_by_account_id_caches_data(
        self,
        container_fix,
        create_product_account,
    ):
        product, _ = await create_product_account()

        detail = await container_fix.account_product_service.get_product_account_by_account_id(product.account_id)
        assert detail
        assert detail.account_id == product.account_id

        cached = await container_fix.accounts_cache_repo.get_product_account_by_account_id(product.account_id)
        assert cached

    @pytest.mark.asyncio
    async def test_create_product_account_validates_category(
        self,
        container_fix,
        create_account_storage,
    ):
        storage = await create_account_storage()
        dto = CreateProductAccountDTO(
            category_id=999999999,
            account_storage_id=storage.account_storage_id,
        )

        with pytest.raises(CategoryNotFound):
            await container_fix.account_product_service.create_product_account(dto, filling_redis=False)

    @pytest.mark.asyncio
    async def test_create_product_account_requires_product_storage(
        self,
        container_fix,
        create_category,
        create_account_storage,
    ):
        category = await create_category(is_product_storage=False)
        storage = await create_account_storage()
        dto = CreateProductAccountDTO(
            category_id=category.category_id,
            account_storage_id=storage.account_storage_id,
        )

        with pytest.raises(TheCategoryNotStorageAccount):
            await container_fix.account_product_service.create_product_account(dto, filling_redis=False)

    @pytest.mark.asyncio
    async def test_delete_product_account_remove_row(
        self,
        container_fix,
        create_product_account,
        session_db_fix,
    ):
        product, _ = await create_product_account()

        await container_fix.account_product_service.delete_product_account(product.account_id)

        result = await session_db_fix.execute(
            select(ProductAccounts).where(ProductAccounts.account_id == product.account_id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_product_account_not_found_raises(self, container_fix):
        with pytest.raises(ProductAccountNotFound):
            await container_fix.account_product_service.delete_product_account(99999999)

    @pytest.mark.asyncio
    async def test_delete_product_accounts_by_category_removes_storages(
        self,
        container_fix,
        create_category,
        create_account_storage,
    ):
        category = await create_category(is_product_storage=True)
        storage = await create_account_storage(status=StorageStatus.FOR_SALE)

        dto = CreateProductAccountDTO(
            category_id=category.category_id,
            account_storage_id=storage.account_storage_id,
        )
        await container_fix.account_product_service.create_product_account(
            data=dto,
            filling_redis=False,
        )

        await container_fix.account_product_service.delete_product_accounts_by_category(category.category_id)

        assert not await container_fix.product_accounts_repo.get_by_category_id(category.category_id)
        assert await container_fix.account_storage_repo.get_by_id(storage.account_storage_id) is None

        folder = container_fix.path_builder.build_path_account(
            status=storage.status,
            type_account_service=storage.type_account_service,
            uuid=storage.storage_uuid,
            return_path_obj=True,
        ).parent

        assert not folder.exists()
