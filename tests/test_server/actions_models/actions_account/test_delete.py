from pathlib import Path

import pytest
import orjson
from sqlalchemy import select

from src.exceptions import TheCategoryStorageAccount, CategoryStoresSubcategories
from src.services.database.system.actions import get_ui_image
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db

from src.services.database.categories.models import (
    Categories, CategoryTranslation,
    ProductAccounts, SoldAccounts, SoldAccountsTranslation, AccountStorage
)



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


@pytest.mark.asyncio
async def test_delete_product_account_success_and_error(create_product_account, create_category):
    """
    Проверяет удаление product_account:
    - успешное удаление из БД и очистка key product_account
    - ошибка при попытке удалить несуществующий аккаунт
    """
    from src.services.database.categories.actions import delete_product_account

    cat = await create_category(filling_redis=True)
    prod, _ = await create_product_account(filling_redis=True, category_id=cat.category_id)
    prod_2 = await create_product_account(filling_redis=True, category_id=cat.category_id)
    account_id = prod.account_id

    # удаляем успешно
    await delete_product_account(account_id)

    async with get_db() as s:
        res = await s.execute(select(ProductAccounts).where(ProductAccounts.account_id == account_id))
        assert res.scalar_one_or_none() is None

    async with get_redis() as r:
        result_redis = await r.get(f"product_accounts_by_category:{cat.category_id}")
        account_list = orjson.loads(result_redis)
        assert len(account_list) == 1 # должен остаться только один

        assert await r.get(f"product_account:{account_id}") is None

    # попытка удалить несуществующий -> ValueError
    with pytest.raises(ValueError):
        await delete_product_account(9999999)


@pytest.mark.asyncio
async def test_delete_sold_account_success_and_redis_update(create_new_user, create_sold_account):
    """
    Проверяет удаление проданного аккаунта:
    - запись удалена из БД (SoldAccounts и SoldAccountsTranslation)
    - Redis обновлён: список владельца и одиночный ключ удалены
    """
    from src.services.database.categories.actions import delete_sold_account

    # создаём user и sold_account через фабрику
    full, _ = await create_sold_account(filling_redis=True, language="ru", name="to_del")
    sold_id = full.sold_account_id
    owner = full.owner_id

    # убедимся что ключи в redis есть
    async with get_redis() as r:
        assert await r.get(f"sold_account:{sold_id}:ru") is not None
        assert await r.get(f"sold_accounts_by_owner_id:{owner}:ru") is not None

    # удаляем
    await delete_sold_account(sold_id)

    # в DB: проверяем что запись проданного аккаунта удалена
    async with get_db() as s:
        res = await s.execute(select(SoldAccounts).where(SoldAccounts.sold_account_id == sold_id))
        assert res.scalar_one_or_none() is None

        res_t = await s.execute(select(SoldAccountsTranslation).where(SoldAccountsTranslation.sold_account_id == sold_id))
        assert res_t.scalar_one_or_none() is None

    # Проверяем redis: одиночный ключ должен быть удалён, а список владельца не должен содержать запись
    async with get_redis() as r:
        assert await r.get(f"sold_account:{sold_id}:ru") is None
        raw_owner = await r.get(f"sold_accounts_by_owner_id:{owner}:ru")
        if raw_owner:
            lst = orjson.loads(raw_owner)
            assert all(item["sold_account_id"] != sold_id for item in lst)

    # попытка удалить несуществующий -> ValueError
    with pytest.raises(ValueError):
        await delete_sold_account(9999999)


@pytest.mark.asyncio
async def test_delete_product_accounts_by_category_success(
        monkeypatch,
        tmp_path,
        create_product_account,
        create_category,
):
    """
    Базовый позитивный сценарий:
    - удаляются AccountStorage связанные с category_id
    - удаляются каталоги на диске
    - вызываются filling_* функции
    - очищается product_account
    """
    from src.services.database.categories.actions.actions_delete import delete_product_accounts_by_category
    from src.services.filesystem.account_actions import create_path_account

    # Создаём категорию
    category = await create_category(filling_redis=True)

    # Создаём 2 product аккаунта
    prod1, acc1 = await create_product_account(
        filling_redis=True,
        category_id=category.category_id
    )
    prod2, acc2 = await create_product_account(
        filling_redis=True,
        category_id=category.category_id
    )

    # Выполняем
    await delete_product_accounts_by_category(category.category_id)

    #  Проверка БД
    async with get_db() as s:
        res = await s.execute(
            select(AccountStorage).where(
                AccountStorage.account_storage_id.in_(
                    [acc1.account_storage.account_storage_id, acc2.account_storage.account_storage_id]
                )
            )
        )
        assert res.scalars().all() == []

        res_prod = await s.execute(
            select(ProductAccounts).where(
                ProductAccounts.account_id.in_([prod1.account_id, prod2.account_id])
            )
        )
        assert res_prod.scalars().all() == []

    # Проверка удаления с диска
    assert not Path(
        create_path_account(acc1.account_storage.status, acc1.type_account_service, acc1.account_storage.storage_uuid)
    ).exists()
    assert not Path(
        create_path_account(acc2.account_storage.status, acc2.type_account_service, acc2.account_storage.storage_uuid)
    ).exists()

    # Проверка Redis
    async with get_redis() as r:
        assert await r.get(f"product_account:{prod1.account_id}") is None
        assert await r.get(f"product_account:{prod2.account_id}") is None
