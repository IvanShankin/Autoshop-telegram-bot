import pytest

from src.database.models.categories import AccountServiceType, StorageStatus
from src.models.create_models.accounts import CreateAccountStorageDTO
from src.models.update_models.accounts import UpdateAccountStorageDTO
from src.repository.database.categories.accounts import TgAccountMediaRepository


class TestAccountStorageService:

    @pytest.mark.asyncio
    async def test_get_account_storage(self, container_fix, create_account_storage):
        storage = await create_account_storage()
        data = await container_fix.account_storage_service.get_account_storage(storage.account_storage_id)
        assert data is not None
        assert data.account_storage_id == storage.account_storage_id

    @pytest.mark.asyncio
    async def test_get_all_phone_numbers_by_service(self, container_fix, create_account_storage):
        storage = await create_account_storage()
        phones = await container_fix.account_storage_service.get_all_phone_numbers_by_service(
            storage.type_account_service,
        )
        assert storage.phone_number in phones

    @pytest.mark.asyncio
    async def test_get_all_tg_ids(self, container_fix, create_account_storage, session_db_fix):
        storage = await create_account_storage()
        storage.tg_id = 123456
        session_db_fix.add(storage)
        await session_db_fix.commit()

        tg_ids = await container_fix.account_storage_service.get_all_tg_ids()
        assert 123456 in tg_ids

    def test_get_type_service_account(self, container_fix):
        assert container_fix.account_storage_service.get_type_service_account("telegram") == AccountServiceType.TELEGRAM
        assert container_fix.account_storage_service.get_type_service_account("invalid") is None

    @pytest.mark.asyncio
    async def test_create_account_storage_telegram_creates_media(
        self,
        container_fix,
    ):
        dto = CreateAccountStorageDTO(
            is_file=True,
            type_account_service=AccountServiceType.TELEGRAM,
            checksum="checksum",
            encrypted_key="key",
            encrypted_key_nonce="nonce",
            phone_number="+79161234567",
        )
        storage = await container_fix.account_storage_service.create_account_storage(dto, make_commit=True)

        media = await TgAccountMediaRepository(
            session_db=container_fix.session_db,
            config=container_fix.config,
        ).get_by_account_storage_id(storage.account_storage_id)
        assert media is not None
        assert storage.storage_uuid

    @pytest.mark.asyncio
    async def test_update_account_storage_calls_fillers(
        self,
        container_fix,
        create_account_storage,
        create_category,
        create_product_account,
        monkeypatch,
    ):
        storage = await create_account_storage()
        category = await create_category(is_product_storage=True)
        await create_product_account(
            category_id=category.category_id,
            account_storage_id=storage.account_storage_id,
        )

        called = {"account": False, "category": False}

        async def _fill_account(account_id):
            called["account"] = True

        async def _fill_category(category_id):
            called["category"] = True

        monkeypatch.setattr(
            container_fix.accounts_cache_filler_service,
            "fill_product_account_by_account_id",
            _fill_account,
        )
        monkeypatch.setattr(
            container_fix.accounts_cache_filler_service,
            "fill_product_accounts_by_category_id",
            _fill_category,
        )

        dto = UpdateAccountStorageDTO(checksum="new-checksum", status=StorageStatus.RESERVED)
        updated = await container_fix.account_storage_service.update_account_storage(
            storage.account_storage_id,
            dto,
        )

        assert updated
        assert updated.checksum == dto.checksum
        assert updated.status == dto.status
        assert called["account"]
        assert called["category"]
