import pytest
from sqlalchemy import select

from src.database.models.categories.product_account import TgAccountMedia
from src.models.create_models.accounts import CreateTgAccountMediaDTO
from src.models.update_models.accounts import UpdateTgAccountMediaDTO


class TestAccountTgMediaService:

    @pytest.mark.asyncio
    async def test_create_and_get_tg_media(
        self,
        container_fix,
        create_account_storage,
        session_db_fix,
    ):
        storage = await create_account_storage()
        dto = CreateTgAccountMediaDTO(
            account_storage_id=storage.account_storage_id,
            tdata_tg_id="tdata",
        )
        media = await container_fix.account_tg_media_service.create_tg_account_media(dto)

        fetched = await container_fix.account_tg_media_service.get_tg_account_media(storage.account_storage_id)
        assert fetched
        assert fetched.tdata_tg_id == dto.tdata_tg_id

        result = await session_db_fix.execute(
            select(TgAccountMedia).where(TgAccountMedia.tg_account_media_id == media.tg_account_media_id)
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio
    async def test_update_tg_media(self, container_fix, create_account_storage):
        storage = await create_account_storage()
        dto = CreateTgAccountMediaDTO(account_storage_id=storage.account_storage_id)
        media = await container_fix.account_tg_media_service.create_tg_account_media(dto)

        update_dto = UpdateTgAccountMediaDTO(tdata_tg_id="new-data")
        updated = await container_fix.account_tg_media_service.update_tg_account_media(media.tg_account_media_id, update_dto)
        assert updated
        assert updated.tdata_tg_id == update_dto.tdata_tg_id
