import pytest
import orjson
from sqlalchemy import select

from src.exceptions import TheCategoryStorageAccount, CategoryStoresSubcategories
from src.services.database.system.actions import get_ui_image
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db

from src.services.database.categories.models import Categories, CategoryTranslation



@pytest.mark.asyncio
async def test_delete_translate_category_success_and_error_when_last_translation(create_category):
    """
    Проверяет удаление перевода:
    - если переводов > 1 — перевод удаляется и ключ в redis удаляется
    - если перевод единственный — ValueError
    """
    from src.services.database.categories.actions import delete_translate_category, add_translation_in_category

    # создаём категорию с переводом ru
    full_cat = await create_category(filling_redis=True, language="ru", name="orig")
    cat_id = full_cat.category_id

    # добавляем перевод 'en'
    en_translation = await add_translation_in_category(
        category_id=cat_id, language="en", name="en name", description="en desc"
    )

    # удаляем en
    await delete_translate_category(cat_id, "en")

    # проверяем в БД, что перевода en нет
    async with get_db() as s:
        res = await s.execute(
            select(CategoryTranslation).where(
                (CategoryTranslation.category_id == cat_id) &
                (CategoryTranslation.lang == "en")
            )
        )
        assert res.scalar_one_or_none() is None

    # проверяем Redis: key для en должен быть удалён
    async with get_redis() as r:
        key = f"category:{cat_id}:en"
        assert await r.get(key) is None

    # попытка удалить последний перевод (ru) должна провалиться
    with pytest.raises(ValueError):
        await delete_translate_category(cat_id, "ru")


@pytest.mark.asyncio
async def test_delete_account_category_various_errors_and_index_shift(create_category, create_product_account):
    """
    Проверяет:
    - нельзя удалить категорию если она is_product_storage или есть product/accounts
    - нельзя удалить если есть дочерние категории
    - при успешном удалении индексы сдвигаются
    """
    from src.services.database.categories.actions import delete_category

    # создаём три основные категории (siblings) для проверки индексов
    cat1 = await create_category(filling_redis=True, language="ru", name="c1")
    cat2 = await create_category(filling_redis=True, language="ru", name="c2")
    cat3 = await create_category(filling_redis=True, language="ru", name="c3")

    # индексы ожидаем 0,1,2
    assert cat1.index == 0
    assert cat2.index == 1
    assert cat3.index == 2

    # попытка удалить категорию-хранилище (если пометить её как is_product_storage) -> создаём такую и пробуем
    storage_cat = await create_category(filling_redis=False, is_product_storage=True, language="ru", name="storage")
    # добавим product в storage_cat
    prod, _ = await create_product_account(filling_redis=True, category_id=storage_cat.category_id)

    with pytest.raises(TheCategoryStorageAccount):
        await delete_category(storage_cat.category_id)

    # создаём родительскую и дочернюю категорию
    parent = await create_category(filling_redis=False, parent_id=None, language="ru", name="parent")
    child = await create_category(filling_redis=False, parent_id=parent.category_id, language="ru", name="child")
    # попытка удалить parent — должен быть ValueError (есть дочерняя)
    with pytest.raises(CategoryStoresSubcategories):
        await delete_category(parent.category_id)

    # успешное удаление middle (cat2) и проверка смещения индексов
    await delete_category(cat2.category_id)

    async with get_db() as s:
        res_all = await s.execute(select(Categories).order_by(Categories.index.asc()))
        remaining = res_all.scalars().all()
        # cat1 должен остаться с index 0, cat3 должен сместиться на 1 (раньше 2)
        ids_idx = {c.category_id: c.index for c in remaining}
        assert ids_idx.get(cat1.category_id) == 0
        assert ids_idx.get(cat3.category_id) == 1

    # проверка redis: ключи по сервису и по категории должны быть обновлены/удалены
    async with get_redis() as r:
        key_list = f"main_categories:ru"
        raw_list = await r.get(key_list)
        assert raw_list is not None
        lst = orjson.loads(raw_list)
        # в списке больше нет cat2
        assert all(el["category_id"] != cat2.category_id for el in lst)


@pytest.mark.asyncio
async def test_delete_category_deleted_ui_image(create_category, create_ui_image):
    from src.services.database.categories.actions import delete_category

    ui_image, _ = await create_ui_image()
    category = await create_category(ui_image_key=ui_image.key)

    await delete_category(category.category_id)

    assert not await get_ui_image(ui_image.key)

