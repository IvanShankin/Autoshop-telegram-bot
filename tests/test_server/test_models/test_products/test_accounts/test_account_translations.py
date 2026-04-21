import pytest

from src.exceptions import TranslationAlreadyExists
from src.exceptions.domain import SoldAccountNotFound
from src.models.create_models.accounts import CreateSoldAccountTranslationDTO
from src.models.update_models.accounts import UpdateSoldAccountTranslationDTO


class TestAccountTranslationsService:

    @pytest.mark.asyncio
    async def test_get_all_translations(
        self,
        container_fix,
        create_sold_account,
    ):
        sold, _ = await create_sold_account()
        translations = await container_fix.account_translations_service.get_all_translations(
            sold_account_id=sold.sold_account_id
        )
        assert translations

    @pytest.mark.asyncio
    async def test_create_translation_persists_and_fills(
        self,
        container_fix,
        create_sold_account,
        monkeypatch,
    ):
        sold, _ = await create_sold_account()
        for_owner = {"account": False, "owner": False}

        async def fill_account(account_id):
            for_owner["account"] = True

        async def fill_owner(owner_id):
            for_owner["owner"] = True

        monkeypatch.setattr(
            container_fix.accounts_cache_filler_service,
            "fill_sold_accounts_by_account_id",
            fill_account,
        )
        monkeypatch.setattr(
            container_fix.accounts_cache_filler_service,
            "fill_sold_accounts_by_owner_id",
            fill_owner,
        )

        dto = CreateSoldAccountTranslationDTO(
            sold_account_id=sold.sold_account_id,
            language="en",
            name="English name",
        )
        created = await container_fix.account_translations_service.create_translation(dto)
        assert created.sold_account_id == sold.sold_account_id
        assert for_owner["account"]
        assert for_owner["owner"]

    @pytest.mark.asyncio
    async def test_create_translation_errors(self, container_fix, create_sold_account):
        dto = CreateSoldAccountTranslationDTO(
            sold_account_id=999999999,
            language="en",
            name="name",
        )
        with pytest.raises(SoldAccountNotFound):
            await container_fix.account_translations_service.create_translation(dto, filling_redis=False)

        sold, _ = await create_sold_account()
        dto = CreateSoldAccountTranslationDTO(
            sold_account_id=sold.sold_account_id,
            language="ru",
            name="duplicate",
        )
        with pytest.raises(TranslationAlreadyExists):
            await container_fix.account_translations_service.create_translation(dto, filling_redis=False)

    @pytest.mark.asyncio
    async def test_update_translation_updates_and_fills(
        self,
        container_fix,
        create_sold_account,
        monkeypatch,
    ):
        sold, _ = await create_sold_account()

        updated_flag = {"account": False, "owner": False}

        async def fill_account(account_id):
            updated_flag["account"] = True

        async def fill_owner(owner_id):
            updated_flag["owner"] = True

        monkeypatch.setattr(
            container_fix.accounts_cache_filler_service,
            "fill_sold_accounts_by_account_id",
            fill_account,
        )
        monkeypatch.setattr(
            container_fix.accounts_cache_filler_service,
            "fill_sold_accounts_by_owner_id",
            fill_owner,
        )

        dto = UpdateSoldAccountTranslationDTO(
            sold_account_id=sold.sold_account_id,
            language="ru",
            name="updated name",
        )
        translation = await container_fix.account_translations_service.update_translation(dto)
        assert translation is not None
        assert translation.name == dto.name
        assert updated_flag["account"]
        assert updated_flag["owner"]
