from pathlib import Path

import pytest
import orjson
from sqlalchemy import select

from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db

from src.services.database.categories.models import ProductAccounts, SoldAccounts, SoldAccountsTranslation, AccountStorage



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
    from src.services.database.categories.actions import delete_product_accounts_by_category
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
