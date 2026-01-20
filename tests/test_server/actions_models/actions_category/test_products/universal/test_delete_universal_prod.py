import pytest
from orjson import orjson
from sqlalchemy import select

from src.services.database.categories.models import ProductUniversal
from src.services.database.categories.models.product_universal import SoldUniversal
from src.services.database.core import get_db
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_delete_prod_universal_success_and_error(create_product_universal, create_category):
    from src.services.database.categories.actions import delete_prod_universal
    from src.services.database.categories.actions import get_categories_by_category_id

    category = await create_category(filling_redis=True)

    prod1, _ = await create_product_universal(category_id=category.category_id, filling_redis=True)
    prod2, _ = await create_product_universal(category_id=category.category_id, filling_redis=True)

    pid = prod1.product_universal_id

    # удаляем
    await delete_prod_universal(pid)

    # DB
    async with get_db() as s:
        res = await s.execute(
            select(ProductUniversal).where(ProductUniversal.product_universal_id == pid)
        )
        assert res.scalar_one_or_none() is None

    # Redis
    async with get_redis() as r:
        raw = await r.get(f"product_universal_by_category:{category.category_id}:ru")
        if raw:
            lst = orjson.loads(raw)
            assert all(i["product_universal_id"] != pid for i in lst)

        assert await r.get(f"product_universal:{pid}:ru") is None

        # тут данные с redis
        cat = await get_categories_by_category_id(category.category_id)
        assert cat.quantity_product == 1

    # ошибка
    with pytest.raises(ValueError):
        await delete_prod_universal(9999999)


@pytest.mark.asyncio
async def test_delete_sold_universal_success_and_error(create_sold_universal):
    from src.services.database.categories.actions import delete_sold_universal

    sold, _ = await create_sold_universal(filling_redis=True)
    sid = sold.sold_universal_id
    owner = sold.owner_id

    # Redis exists
    async with get_redis() as r:
        assert await r.get(f"sold_universal:{sid}:ru") is not None
        assert await r.get(f"sold_universal_by_owner_id:{owner}:ru") is not None

    # delete
    await delete_sold_universal(sid)

    # DB
    async with get_db() as s:
        res = await s.execute(
            select(SoldUniversal).where(SoldUniversal.sold_universal_id == sid)
        )
        assert res.scalar_one_or_none() is None

    # Redis
    async with get_redis() as r:
        assert await r.get(f"sold_universal:{sid}:ru") is None

        raw = await r.get(f"sold_universal_by_owner_id:{owner}:ru")
        if raw:
            lst = orjson.loads(raw)
            assert all(i["sold_universal_id"] != sid for i in lst)

    # ошибка
    with pytest.raises(ValueError):
        await delete_sold_universal(9999999)
