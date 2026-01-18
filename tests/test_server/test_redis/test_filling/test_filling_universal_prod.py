import orjson
import pytest
from sqlalchemy.orm import selectinload

from tests.helpers.helper_functions import comparison_models
from src.services.database.categories.models.product_universal import SoldUniversal
from src.services.database.core import get_db
from src.services.redis.core_redis import get_redis
from src.services.redis.filling.filling_universal import filling_product_universal_by_category, \
    filling_universal_by_product_id, filling_sold_universal_by_owner_id, filling_sold_universal_by_universal_id


@pytest.mark.asyncio
async def test_filling_product_universal_by_category(create_category, create_product_universal):
    category = await create_category(filling_redis=False)

    products = []
    for i in range(3):
        universal_product_small, _ = await create_product_universal(
            filling_redis=False,
            category_id=category.category_id,
        )
        products.append(universal_product_small)

    other_universal_product_small, _ = await create_product_universal(filling_redis=False)

    await filling_product_universal_by_category()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"product_universal_by_category:{category.category_id}"
        )
        redis_result = orjson.loads(val)

    for prod in products:
        assert any(comparison_models(prod.model_dump(), redis) for redis in redis_result)

    assert not other_universal_product_small in redis_result


@pytest.mark.asyncio
async def test_filling_product_account_by_account_id(create_product_universal, create_category):
    category = await create_category(is_product_storage=True)
    _, product = await create_product_universal(
        filling_redis=False,
        category_id=category.category_id,
    )

    await filling_universal_by_product_id(product.product_universal_id)

    async with get_redis() as session_redis:
        val = await session_redis.get(f"product_universal:{product.product_universal_id}")

    assert comparison_models(product.model_dump(), orjson.loads(val))



@pytest.mark.asyncio
async def test_filling_sold_universal_by_owner_id(create_new_user, create_sold_universal):
    user = await create_new_user()

    sold_1, _ = await create_sold_universal(filling_redis=False, owner_id=user.user_id)
    sold_2, _ = await create_sold_universal(filling_redis=False, owner_id=user.user_id)
    sold_3, _ = await create_sold_universal(filling_redis=False, owner_id=user.user_id)

    async with get_db() as session:
        sold = await session.get(
            SoldUniversal,
            sold_3.sold_universal_id,
            options=[selectinload(SoldUniversal.storage)]
        )
        sold.storage.is_active = False
        await session.commit()

    await filling_sold_universal_by_owner_id(user.user_id)

    async with get_redis() as session_redis:
        key = f"sold_universal_by_owner_id:{user.user_id}:ru"
        val = await session_redis.get(key)

    assert val is not None, f"missing redis key {key}"

    items = orjson.loads(val)

    assert 2 == len(items)

    assert comparison_models(sold_2.model_dump(), items[0])


@pytest.mark.asyncio
async def test_filling_sold_universal_by_universal_id(create_sold_universal):
    _, sold_universal = await create_sold_universal(filling_redis=False)

    await filling_sold_universal_by_universal_id(sold_universal.sold_universal_id)

    async with get_redis() as session_redis:
        key = f"sold_universal:{sold_universal.sold_universal_id}:ru"
        val = await session_redis.get(key)

    assert val is not None, f"missing redis key {key}"

    data = orjson.loads(val)

    assert comparison_models(sold_universal.model_dump(), data)
