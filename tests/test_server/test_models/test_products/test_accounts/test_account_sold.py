import pytest
from sqlalchemy import select

from src.database.models.categories import AccountServiceType
from src.database.models.categories.product_account import StorageStatus, SoldAccounts
from src.exceptions.domain import SoldAccountNotFound
from src.exceptions import UserNotFound
from src.models.create_models.accounts import CreateSoldAccountWithTranslationDTO


class TestAccountSoldService:

    @pytest.mark.asyncio
    async def test_get_sold_accounts_by_owner_id(
        self,
        container_fix,
        create_sold_account,
    ):
        sold, _ = await create_sold_account()
        items = await container_fix.account_sold_service.get_sold_accounts_by_owner_id(
            owner_id=sold.owner_id,
            language="ru",
        )
        assert items
        assert any(entry.sold_account_id == sold.sold_account_id for entry in items)

    @pytest.mark.asyncio
    async def test_get_sold_account_by_page_and_count(
        self,
        container_fix,
        create_sold_account,
    ):
        sold, _ = await create_sold_account()
        page = await container_fix.account_sold_service.get_sold_account_by_page(
            user_id=sold.owner_id,
            type_account_service=AccountServiceType.TELEGRAM,
            page=1,
            language="ru",
        )
        assert len(page) >= 1

        count = await container_fix.account_sold_service.get_count_sold_account(
            user_id=sold.owner_id,
            type_account_service=AccountServiceType.TELEGRAM,
        )
        assert count >= 1

    @pytest.mark.asyncio
    async def test_get_sold_account_by_account_id(
        self,
        container_fix,
        create_sold_account,
    ):
        sold, _ = await create_sold_account()
        detail = await container_fix.account_sold_service.get_sold_account_by_account_id(
            sold_account_id=sold.sold_account_id,
            language="ru",
        )
        assert detail
        assert detail.sold_account_id == sold.sold_account_id

    @pytest.mark.asyncio
    async def test_get_types_account_service_where_the_user_purchase(
        self,
        container_fix,
        create_sold_account,
    ):
        sold, _ = await create_sold_account()
        types = await container_fix.account_sold_service.get_types_account_service_where_the_user_purchase(
            user_id=sold.owner_id,
        )
        assert AccountServiceType.TELEGRAM in types

    @pytest.mark.asyncio
    async def test_create_sold_account_requires_user(
        self,
        container_fix,
        create_sold_account,
    ):
        _, full = await create_sold_account()
        dto = CreateSoldAccountWithTranslationDTO(
            owner_id=999999999,
            account_storage_id=full.account_storage.account_storage_id,
            language="ru",
            name="test",
        )
        with pytest.raises(UserNotFound):
            await container_fix.account_sold_service.create_sold_account(dto, filling_redis=False)

    @pytest.mark.asyncio
    async def test_create_sold_account_persists(
        self,
        container_fix,
        create_new_user,
        create_account_storage,
        session_db_fix,
    ):
        user = await create_new_user()
        storage = await create_account_storage(status=StorageStatus.BOUGHT)
        dto = CreateSoldAccountWithTranslationDTO(
            owner_id=user.user_id,
            account_storage_id=storage.account_storage_id,
            language="en",
            name="english name",
        )
        sold = await container_fix.account_sold_service.create_sold_account(dto, filling_redis=False)

        result = await session_db_fix.execute(
            select(SoldAccounts).where(SoldAccounts.sold_account_id == sold.sold_account_id)
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_delete_sold_account_removes(self, container_fix, create_sold_account):
        sold, _ = await create_sold_account()
        await container_fix.account_sold_service.delete_sold_account(sold.sold_account_id)
        assert await container_fix.sold_accounts_repo.get_by_id(sold.sold_account_id) is None

    @pytest.mark.asyncio
    async def test_delete_sold_account_not_found(self, container_fix):
        with pytest.raises(SoldAccountNotFound):
            await container_fix.account_sold_service.delete_sold_account(999999999)
