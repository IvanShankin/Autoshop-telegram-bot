import orjson
import pytest

from src.services.redis.filling import filling_main_categories, filling_categories_by_parent, \
    filling_category_by_category
from tests.helpers.helper_functions import comparison_models
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_filling_main_categories(create_category):
    category = await create_category(filling_redis=False, is_main=True)

    # Execute
    await filling_main_categories(category.category_id)

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"main_categories:ru"
        )

    assert comparison_models(category.model_dump(), orjson.loads(val)[0], ['quantity_product_account'])

@pytest.mark.asyncio
async def test_filling_categories_by_parent(create_category):
    category_parent = await create_category(filling_redis=False)
    category = await create_category(filling_redis=False, parent_id=category_parent.category_id)

    # Execute
    await filling_categories_by_parent(category.category_id)

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"categories_by_parent:{category_parent.category_id}:ru"
        )

    assert comparison_models(category.model_dump(), orjson.loads(val)[0], ['quantity_product_account'])


@pytest.mark.asyncio
async def test_filling_category_by_category(create_category):
    category = await create_category(filling_redis=False, language='ru')

    await filling_category_by_category([category.category_id])

    async with get_redis() as session_redis:
        val = await session_redis.get(
            f"category:{category.category_id}:ru"
        )

    assert comparison_models(category.model_dump(), orjson.loads(val), ['quantity_product_account'])

