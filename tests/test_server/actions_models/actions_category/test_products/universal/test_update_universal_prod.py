import orjson
import pytest
from sqlalchemy import select

from src.services.database.categories.models import UniversalStorage
from src.services.database.core import get_db
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_add_product_universal(create_category, create_product_universal):
    from src.services.database.categories.actions import update_universal_storage

    # заполнит redis и БД
    small, prod_full = await create_product_universal()

    await update_universal_storage(
        prod_full.universal_storage_id,
        checksum="checksum_new",
        is_active=False
    )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(UniversalStorage).where(UniversalStorage.universal_storage_id == prod_full.universal_storage_id)
        )
        storage_db: UniversalStorage = result.scalar_one_or_none()
        assert storage_db is not None
        assert storage_db.checksum == "checksum_new"
        assert storage_db.is_active == False

    async with get_redis() as session_redis:
        result_redis = await session_redis.get(f"product_universal:{prod_full.universal_storage_id}")
        assert result_redis

        prod_redis = orjson.loads(result_redis)
        assert prod_redis["universal_storage"]["checksum"] == "checksum_new"
        assert prod_redis["universal_storage"]["is_active"] == False



