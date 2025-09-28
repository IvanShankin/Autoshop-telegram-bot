import pytest
import orjson
from sqlalchemy import select

from src.redis_dependencies.core_redis import get_redis
from src.services.database.database import get_db
from src.services.selling_accounts.actions import (
    delete_account_service,
    delete_translate_category,
    delete_account_category,
    delete_product_account,
    delete_sold_account,
    add_translation_in_account_category,  # используется в тестах
)
from src.services.selling_accounts.models import (
    AccountServices, AccountCategories, AccountCategoryTranslation,
    ProductAccounts, SoldAccounts, SoldAccountsTranslation
)


@pytest.mark.asyncio
async def test_delete_account_service_success_and_index_shift(create_type_account_service, create_account_service):
    t1 = await create_type_account_service(name="t1")
    svc1 = await create_account_service(filling_redis=True, name="svc1", type_account_service_id=t1.type_account_service_id)
    t2 = await create_type_account_service(name="t2")
    svc2 = await create_account_service(filling_redis=True, name="svc2", type_account_service_id=t2.type_account_service_id)

    # убедимся что индексы 0 и 1
    assert svc1.index == 0
    assert svc2.index == 1

    # удаляем сервис с индексом 0 (svc1)
    await delete_account_service(svc1.account_service_id)

    # проверяем БД: svc1 нет, svc2 индекс стал 0
    async with get_db() as s:
        res = await s.execute(select(AccountServices).where(AccountServices.account_service_id == svc1.account_service_id))
        assert res.scalar_one_or_none() is None

        res2 = await s.execute(select(AccountServices).where(AccountServices.account_service_id == svc2.account_service_id))
        svc2_db = res2.scalar_one_or_none()
        assert svc2_db is not None
        assert svc2_db.index == 0

    # проверяем Redis
    async with get_redis() as r:
        raw_list = await r.get("account_services")
        assert raw_list is not None
        list_services = orjson.loads(raw_list)
        # svc1 не должен присутствовать, svc2 присутствует и index == 0
        ids = [s["account_service_id"] for s in list_services]
        assert svc1.account_service_id not in ids
        found = [s for s in list_services if s["account_service_id"] == svc2.account_service_id]
        assert found
        assert found[0]["index"] == 0

        # одиночный ключ удалён
        single = await r.get(f"account_service:{svc1.account_service_id}")
        assert single is None


@pytest.mark.asyncio
async def test_delete_account_service_error_when_has_categories(create_account_service, create_account_category):
    """
    Нельзя удалить сервис если у него есть категории -> ValueError
    """
    svc = await create_account_service(filling_redis=False)
    # создаём категорию привязанную к svc
    cat = await create_account_category(filling_redis=False, account_service_id=svc.account_service_id)

    with pytest.raises(ValueError):
        await delete_account_service(svc.account_service_id)


@pytest.mark.asyncio
async def test_delete_translate_category_success_and_error_when_last_translation(create_account_category):
    """
    Проверяет удаление перевода:
    - если переводов > 1 — перевод удаляется и ключ в redis удаляется
    - если перевод единственный — ValueError
    """
    # создаём категорию с переводом ru
    full_cat = await create_account_category(filling_redis=True, language="ru", name="orig")
    cat_id = full_cat.account_category_id

    # добавляем перевод 'en'
    en_translation = await add_translation_in_account_category(
        account_category_id=cat_id, language="en", name="en name", description="en desc"
    )

    # удаляем en
    await delete_translate_category(cat_id, "en")

    # проверяем в БД, что перевода en нет
    async with get_db() as s:
        res = await s.execute(
            select(AccountCategoryTranslation).where(
                (AccountCategoryTranslation.account_category_id == cat_id) &
                (AccountCategoryTranslation.lang == "en")
            )
        )
        assert res.scalar_one_or_none() is None

    # проверяем Redis: key для en должен быть удалён
    async with get_redis() as r:
        key = f"account_categories_by_category_id:{cat_id}:en"
        assert await r.get(key) is None

    # попытка удалить последний перевод (ru) должна провалиться
    with pytest.raises(ValueError):
        await delete_translate_category(cat_id, "ru")


@pytest.mark.asyncio
async def test_delete_account_category_various_errors_and_index_shift(create_account_service, create_account_category, create_product_account):
    """
    Проверяет:
    - нельзя удалить категорию если она is_accounts_storage или есть product/accounts
    - нельзя удалить если есть дочерние категории
    - при успешном удалении индексы сдвигаются
    """
    svc = await create_account_service(filling_redis=False)
    # создаём три основные категории (siblings) для проверки индексов
    cat1 = await create_account_category(filling_redis=True, account_service_id=svc.account_service_id, language="ru", name="c1")
    cat2 = await create_account_category(filling_redis=True, account_service_id=svc.account_service_id, language="ru", name="c2")
    cat3 = await create_account_category(filling_redis=True, account_service_id=svc.account_service_id, language="ru", name="c3")

    # индексы ожидаем 0,1,2
    assert cat1.index == 0
    assert cat2.index == 1
    assert cat3.index == 2

    # попытка удалить категорию-хранилище (если пометить её как is_accounts_storage) -> создаём такую и пробуем
    storage_cat = await create_account_category(filling_redis=False, account_service_id=svc.account_service_id, is_accounts_storage=True, language="ru", name="storage")
    # добавим product в storage_cat
    prod = await create_product_account(filling_redis=True, account_category_id=storage_cat.account_category_id, hash_login="l", hash_password="p")

    with pytest.raises(ValueError):
        await delete_account_category(storage_cat.account_category_id)

    # создаём родительскую и дочернюю категорию
    parent = await create_account_category(filling_redis=False, account_service_id=svc.account_service_id, parent_id=None, language="ru", name="parent")
    child = await create_account_category(filling_redis=False, account_service_id=svc.account_service_id, parent_id=parent.account_category_id, language="ru", name="child")
    # попытка удалить parent — должен быть ValueError (есть дочерняя)
    with pytest.raises(ValueError):
        await delete_account_category(parent.account_category_id)

    # успешное удаление middle (cat2) и проверка смещения индексов
    await delete_account_category(cat2.account_category_id)

    async with get_db() as s:
        res_all = await s.execute(select(AccountCategories).where(AccountCategories.account_service_id == svc.account_service_id).order_by(AccountCategories.index.asc()))
        remaining = res_all.scalars().all()
        # cat1 должен остаться с index 0, cat3 должен сместиться на 1 (раньше 2)
        ids_idx = {c.account_category_id: c.index for c in remaining}
        assert ids_idx.get(cat1.account_category_id) == 0
        assert ids_idx.get(cat3.account_category_id) == 1

    # проверка redis: ключи по сервису и по категории должны быть обновлены/удалены
    async with get_redis() as r:
        key_list = f"account_categories_by_service_id:{svc.account_service_id}:ru"
        raw_list = await r.get(key_list)
        assert raw_list is not None
        lst = orjson.loads(raw_list)
        # в списке больше нет cat2
        assert all(el["account_category_id"] != cat2.account_category_id for el in lst)


@pytest.mark.asyncio
async def test_delete_product_account_success_and_error(create_product_account, create_account_category):
    """
    Проверяет удаление product_account:
    - успешное удаление из БД и очистка key product_accounts_by_account_id
    - ошибка при попытке удалить несуществующий аккаунт
    """
    cat = await create_account_category(filling_redis=True)
    prod = await create_product_account(filling_redis=True, account_category_id=cat.account_category_id)
    prod_2 = await create_product_account(filling_redis=True, account_category_id=cat.account_category_id)
    account_id = prod.account_id

    # удаляем успешно
    await delete_product_account(account_id)

    async with get_db() as s:
        res = await s.execute(select(ProductAccounts).where(ProductAccounts.account_id == account_id))
        assert res.scalar_one_or_none() is None

    async with get_redis() as r:
        result_redis = await r.get(f"product_accounts_by_category_id:{cat.account_category_id}")
        account_list = orjson.loads(result_redis)
        assert len(account_list) == 1 # должен остаться только один

        assert await r.get(f"product_accounts_by_account_id:{account_id}") is None

    # попытка удалить несуществующий -> ValueError
    with pytest.raises(ValueError):
        await delete_product_account(9999999)


@pytest.mark.asyncio
async def test_delete_sold_account_success_and_redis_update(create_new_user, create_type_account_service, create_sold_account):
    """
    Проверяет удаление проданного аккаунта:
    - запись удалена из БД (SoldAccounts и SoldAccountsTranslation)
    - Redis обновлён: список владельца и одиночный ключ удалены
    """
    # создаём user и sold_account через фабрику
    full = await create_sold_account(filling_redis=True, language="ru", name="to_del")
    sold_id = full.sold_account_id
    owner = full.owner_id

    # убедимся что ключи в redis есть
    async with get_redis() as r:
        assert await r.get(f"sold_accounts_by_accounts_id:{sold_id}:ru") is not None
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
        assert await r.get(f"sold_accounts_by_accounts_id:{sold_id}:ru") is None
        raw_owner = await r.get(f"sold_accounts_by_owner_id:{owner}:ru")
        if raw_owner:
            lst = orjson.loads(raw_owner)
            assert all(item["sold_account_id"] != sold_id for item in lst)

    # попытка удалить несуществующий -> ValueError
    with pytest.raises(ValueError):
        await delete_sold_account(9999999)
