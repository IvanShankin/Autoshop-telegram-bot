import pytest

from tests.helpers.helper_fixture import create_new_user
from tests.helpers.helper_functions import comparison_models


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_universal_by_category_id(use_redis, create_category, create_product_universal):
    from src.services.database.categories.actions import get_product_universal_by_category_id

    category = await create_category()
    prod_1, _ = await create_product_universal(use_redis, category_id=category.category_id)
    prod_2, _ = await create_product_universal(use_redis, category_id=category.category_id)
    prod_other, _ = await create_product_universal(use_redis)

    list_products = await get_product_universal_by_category_id(category.category_id)
    # приводим к серилизованной форме для сравнения
    list_products = [p.model_dump() for p in list_products]

    assert len(list_products) == 2
    assert any(comparison_models(prod_1.model_dump(), p) for p in list_products)
    assert any(comparison_models(prod_2.model_dump(), p) for p in list_products)


@pytest.mark.asyncio
async def test_get_full_product_universal_by_category_id(create_category, create_product_universal):
    from src.services.database.categories.actions import get_product_universal_by_category_id

    category = await create_category()
    _, full_1 = await create_product_universal(category_id=category.category_id)
    _, full_2 = await create_product_universal(category_id=category.category_id)
    _, full_other = await create_product_universal()

    list_products = await get_product_universal_by_category_id(category.category_id, get_full=True, language="ru")
    list_products = [p.model_dump() for p in list_products]

    assert len(list_products) == 2
    assert any(comparison_models(full_1.model_dump(), p) for p in list_products)
    assert any(comparison_models(full_2.model_dump(), p) for p in list_products)


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_product_universal_by_product_id(use_redis, create_category, create_product_universal):
    from src.services.database.categories.actions import get_product_universal_by_product_id

    category = await create_category()
    _, full = await create_product_universal(use_redis, category_id=category.category_id)
    _, full_other = await create_product_universal(use_redis)

    result = await get_product_universal_by_product_id(full.product_universal_id)

    # фабрика возвращает ProductUniversalFull — сравним Pydantic-объекты
    assert full.model_dump() == result.model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_universal_by_owner_id(use_redis, create_new_user, create_sold_universal):
    from src.services.database.categories.actions import get_sold_universal_by_owner_id

    owner = await create_new_user()
    sold_1, _ = await create_sold_universal(use_redis, owner_id=owner.user_id)
    sold_2, _ = await create_sold_universal(use_redis, owner_id=owner.user_id)
    sold_other, _ = await create_sold_universal(use_redis)

    list_sold = await get_sold_universal_by_owner_id(owner.user_id, owner.language)
    list_sold = [s.model_dump() for s in list_sold]

    # должен быть отсортирован по убыванию даты (новые первыми)
    assert len(list_sold) == 2
    assert sold_2.model_dump() == list_sold[0]
    assert sold_1.model_dump() == list_sold[1]


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_universal_by_page(use_redis, create_new_user, create_sold_universal):
    from src.services.database.categories.actions import get_sold_universal_by_page

    owner = await create_new_user()
    sold_1, _ = await create_sold_universal(use_redis, owner_id=owner.user_id)
    sold_2, _ = await create_sold_universal(use_redis, owner_id=owner.user_id)
    sold_other, _ = await create_sold_universal(use_redis)

    page_list = await get_sold_universal_by_page(owner.user_id, 1, owner.language)
    page_list = [s.model_dump() for s in page_list]

    # должен быть отсортирован по убыванию даты (новые первыми)
    assert len(page_list) == 2
    assert sold_2.model_dump() == page_list[0]
    assert sold_1.model_dump() == page_list[1]


@pytest.mark.asyncio
async def test_get_count_sold_universal(create_new_user, create_sold_universal):
    from src.services.database.categories.actions import get_count_sold_universal

    user = await create_new_user()

    for i in range(3):
        _, sold_full = await create_sold_universal(owner_id=user.user_id)

    # этот продукт не должны посчитать
    _, sold_full = await create_sold_universal(owner_id=user.user_id, is_active=False)

    quantity = await get_count_sold_universal(user.user_id)

    assert quantity == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('use_redis', (True, False))
async def test_get_sold_universal_by_universal_id(use_redis, create_sold_universal):
    from src.services.database.categories.actions import get_sold_universal_by_universal_id

    _, sold_full = await create_sold_universal(use_redis)
    _, sold_other = await create_sold_universal(use_redis)

    result = await get_sold_universal_by_universal_id(sold_full.sold_universal_id, language="ru")

    assert sold_full.model_dump() == result.model_dump()
