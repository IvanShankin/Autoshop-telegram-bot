import pytest
import orjson
from sqlalchemy import select

from src.services.database.categories.models import AccountStorage, TgAccountMedia
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.categories.models import  ProductAccountFull


class TestUpdateAccountStorage:
    @pytest.mark.asyncio
    async def test_update_account_storage_sold_account(self, create_sold_account, create_account_storage):
        from src.services.database.categories.actions import update_account_storage
        account_storage = await create_account_storage()
        _, full_account = await create_sold_account(
            filling_redis=True, account_storage_id=account_storage.account_storage_id, language="ru"
        )
        sold_account_id = full_account.sold_account_id

        # делаем аккаунт невалидным
        await update_account_storage(account_storage_id=account_storage.account_storage_id, is_active=False)

        async with get_db() as session:
            res_db = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == account_storage.account_storage_id))
            account_storage: AccountStorage = res_db.scalar_one()
            assert account_storage.is_active == False

        async with get_redis() as r:
            # в redis не должны ничего хранить, т.к. мы установили is_valid == False
            json_str = await r.get(f"sold_account:{sold_account_id}:ru")
            assert not json_str

            json_str = await r.get(f"sold_accounts_by_owner_id:{full_account.owner_id}:ru")
            assert not json_str


    @pytest.mark.asyncio
    async def test_update_account_storage_product_account(self, create_product_account, create_account_storage):
        from src.services.database.categories.actions import update_account_storage
        account_storage = await create_account_storage()
        _, full_account = await create_product_account(filling_redis=True, account_storage_id=account_storage.account_storage_id)
        product_account_id = full_account.account_id

        # делаем аккаунт невалидным
        await update_account_storage(account_storage_id=account_storage.account_storage_id, is_valid=False)

        async with get_db() as session:
            res_db = await session.execute(
                select(AccountStorage).where(AccountStorage.account_storage_id == account_storage.account_storage_id))
            account_storage: AccountStorage = res_db.scalar_one()
            assert account_storage.is_valid == False

        async with get_redis() as r:
            raw_single = await r.get(f"product_account:{product_account_id}")
            product_account = ProductAccountFull(**orjson.loads(raw_single))
            assert product_account.account_storage.is_valid == False


@pytest.mark.asyncio
async def test_update_tg_account_media(create_tg_account_media):
    from src.services.database.categories.actions import update_tg_account_media

    tg_media = await create_tg_account_media()

    await update_tg_account_media(
        tg_account_media_id=tg_media.tg_account_media_id,
        tdata_tg_id='123456789',
        session_tg_id='987654321'
    )
    async with get_db() as db_session:
        res_db = await db_session.execute(
            select(TgAccountMedia).where(TgAccountMedia.tg_account_media_id == tg_media.tg_account_media_id))
        account_storage: TgAccountMedia = res_db.scalar_one()
        assert account_storage.tdata_tg_id == '123456789'
        assert account_storage.session_tg_id == '987654321'
