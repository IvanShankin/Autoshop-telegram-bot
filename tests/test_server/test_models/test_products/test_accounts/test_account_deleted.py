import pytest
from sqlalchemy import select

from src.models.create_models.accounts import CreateDeletedAccountDTO
from src.database.models.categories.product_account import DeletedAccounts


class TestAccountDeletedService:

    @pytest.mark.asyncio
    async def test_create_and_get_deleted_account(
        self,
        container_fix,
        create_account_storage,
        session_db_fix,
    ):
        storage = await create_account_storage()
        dto = CreateDeletedAccountDTO(
            account_storage_id=storage.account_storage_id,
            category_name="test-category",
            description="removed",
        )

        deleted = await container_fix.account_deleted_service.create_deleted_account(dto)

        by_id = await container_fix.account_deleted_service.get_deleted_account(deleted.deleted_account_id)
        assert by_id is not None
        assert by_id.category_name == dto.category_name

        by_storage = await container_fix.account_deleted_service.get_deleted_account_by_storage_id(storage.account_storage_id)
        assert by_storage is not None

        result = await session_db_fix.execute(
            select(DeletedAccounts).where(DeletedAccounts.deleted_account_id == deleted.deleted_account_id)
        )
        assert result.scalar_one_or_none() is not None
