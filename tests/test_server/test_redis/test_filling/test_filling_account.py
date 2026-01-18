import orjson
import pytest

from src.services.redis.filling import  filling_product_accounts_by_category_id, filling_product_account_by_account_id,\
    filling_sold_accounts_by_owner_id, filling_sold_account_by_account_id
from tests.helpers.helper_functions import comparison_models
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_filling_product_accounts_by_category_id(create_category, create_product_account):
    category = await create_category(filling_redis=False)

    account_products = []
    for i in range(3):
        product, _ = await create_product_account(
            filling_redis=False,
            category_id=category.category_id,
        )
        account_products.append(product)

    other_account_product, _ = await create_product_account(filling_redis=False)

    await filling_product_accounts_by_category_id()

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"product_accounts_by_category:{category.category_id}"
        )
        redis_result = orjson.loads(val)

    for prod in account_products:
        assert any(comparison_models(prod.to_dict(), redis)  for redis in redis_result )

    assert not other_account_product in redis_result


@pytest.mark.asyncio
async def test_filling_product_account_by_account_id(create_product_account, create_category):
    category = await create_category(is_product_storage=True)
    _, product = await create_product_account(
        filling_redis=False,
        category_id=category.category_id,
    )

    await filling_product_account_by_account_id(product.account_id)

    async with get_redis() as session_redis:
        val = await session_redis.get(f"product_account:{product.account_id}")

    assert comparison_models(product.model_dump(), orjson.loads(val))


@pytest.mark.asyncio
async def test_filling_sold_accounts_by_owner_id(create_new_user, create_sold_account):
    user = await create_new_user()
    sold_account_1, _ = await create_sold_account(filling_redis=False, owner_id=user.user_id)
    sold_account_2, _ = await create_sold_account(filling_redis=False, owner_id=user.user_id)
    sold_account_3, _ = await create_sold_account(filling_redis=False, is_active=False, owner_id=user.user_id)

    await filling_sold_accounts_by_owner_id(user.user_id)

    async with get_redis() as session_redis:
        key = f"sold_accounts_by_owner_id:{user.user_id}:ru"
        val = await session_redis.get(key)

    assert val is not None, f"missing redis key {key}"
    items = orjson.loads(val)

    assert 2 == len(items)

    assert comparison_models(sold_account_2.model_dump(), items[0])


@pytest.mark.asyncio
async def test_filling_sold_account_by_account_id(create_sold_account):
    _, sold_account = await create_sold_account(filling_redis=False)
    await filling_sold_account_by_account_id(sold_account.sold_account_id)

    async with get_redis() as session_redis:
        key = f"sold_account:{sold_account.sold_account_id}:ru"
        val = await session_redis.get(key)

    data = orjson.loads(val)

    assert comparison_models(sold_account.model_dump(), data)

