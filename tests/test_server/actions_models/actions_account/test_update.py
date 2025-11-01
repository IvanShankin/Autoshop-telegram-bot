import pytest
import orjson
from sqlalchemy import select

from src.services.database.selling_accounts.models.models import AccountStorage
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.models import (AccountServices, AccountCategories,AccountCategoryTranslation,
                                                           ProductAccountFull)


class TestUpdateAccountService:
    @pytest.mark.asyncio
    async def test_update_account_service_change_index_up_and_down(self, create_type_account_service, create_account_service):
        from src.services.database.selling_accounts.actions import update_account_service
        # создаём 3 сервиса с индексами 0,1,2
        s1 = await create_account_service(filling_redis=True, name="s1", index=0)
        s2 = await create_account_service(filling_redis=True, name="s2", index=1)
        s3 = await create_account_service(filling_redis=True, name="s3", index=2)

        # Переместим s3 (index 2) в начало (index 0)
        updated = await update_account_service(s3.account_service_id, index=0)
        assert updated.index == 0

        # Проверим в БД: ожидаем порядок: s3(0), s1(1), s2(2)
        async with get_db() as session:
            res = await session.execute(select(AccountServices).order_by(AccountServices.index.asc()))
            rows: list[AccountServices] = res.scalars().all()
            assert rows[0].account_service_id == s3.account_service_id
            assert rows[0].index == 0
            assert rows[1].index == 1
            assert rows[2].index == 2

        # Проверим Redis: account_services должен быть отсортирован по index asc
        async with get_redis() as r:
            raw = await r.get("account_services")
            assert raw
            lst = orjson.loads(raw)
            # первый элемент должен быть s3 (индекс 0)
            assert lst[0]["account_service_id"] == s3.account_service_id
            assert lst[0]["index"] == 0
            assert lst[1]["index"] == 1
            assert lst[2]["index"] == 2

        # переместим s3 (текущий index 0) в конец index=2
        updated2 = await update_account_service(s3.account_service_id, index=2)
        assert updated2.index == 2

        # проверим DB порядок: now expected s1(0), s2(1), s3(2)
        async with get_db() as session:
            res = await session.execute(select(AccountServices).order_by(AccountServices.index.asc()))
            rows = res.scalars().all()
            assert rows[0].index == 0
            assert rows[1].index == 1
            assert rows[2].index == 2
            assert rows[2].account_service_id == s3.account_service_id

        # Redis должен отражать окончательный порядок
        async with get_redis() as r:
            raw = await r.get("account_services")
            lst = orjson.loads(raw)
            assert lst[2]["account_service_id"] == s3.account_service_id
            assert [item["index"] for item in lst] == [0, 1, 2]


    @pytest.mark.asyncio
    async def test_update_account_service_name_show_only_updates_single_redis_key(self,create_type_account_service, create_account_service):
        from src.services.database.selling_accounts.actions import update_account_service

        t1 = await create_type_account_service(name="t1b")
        s = await create_account_service(filling_redis=True, name="orig_name", type_account_service_id=t1.type_account_service_id, index=0)

        # изменить только имя и показать (индекс не указан)
        updated = await update_account_service(s.account_service_id, name="new_name", show=False)
        assert updated.name == "new_name"
        assert updated.show is False

        async with get_db() as session:
            res = await session.execute(select(AccountServices).where(AccountServices.account_service_id == s.account_service_id))
            svc = res.scalar_one()
            assert svc.name == "new_name"
            assert svc.show is False

        async with get_redis() as r:
            raw = await r.get(f"account_service:{s.account_service_id}")
            assert raw
            obj = orjson.loads(raw)
            assert obj["name"] == "new_name"
            assert obj["show"] is False

        # порядок списка account_services должен оставаться действительным, а индексы — неизменными
        raw_all = await r.get("account_services")
        lst = orjson.loads(raw_all)
        # поиск услуги в списке
        found = [x for x in lst if x["account_service_id"] == s.account_service_id]
        assert found and found[0]["name"] == "new_name"

class TestUpdateAccountCategory:
    @pytest.mark.asyncio
    async def test_update_account_category_index_reorder_and_redis(self, create_account_service, create_account_category):
        from src.services.database.selling_accounts.actions import update_account_category
        # Создаём один сервис и три категории (main) с индексами 0,1,2
        svc = await create_account_service(filling_redis=True, name="svc_cat_test")
        c1 = await create_account_category(filling_redis=True, account_service_id=svc.account_service_id, language="ru", name="c1")
        c2 = await create_account_category(filling_redis=True, account_service_id=svc.account_service_id, language="ru", name="c2")
        c3 = await create_account_category(filling_redis=True, account_service_id=svc.account_service_id, language="ru", name="c3")

        # перемещение c3 -> index 0
        updated = await update_account_category(c3.account_category_id, index=0)
        assert updated.index == 0

        # проверка базы данных: категории для этой услуги, упорядоченные по индексу (возрастание): c3(0), c1(1), c2(2)
        async with get_db() as session:
            res = await session.execute(select(AccountCategories).where(AccountCategories.account_service_id == svc.account_service_id).order_by(AccountCategories.index.asc()))
            rows = res.scalars().all()
            assert rows[0].account_category_id == c3.account_category_id
            assert rows[0].index == 0
            assert rows[1].index == 1
            assert rows[2].index == 2

        # Redis: account_categories_by_service_id:{service_id}:ru следует сортировать по возрастанию индекса
        async with get_redis() as r:
            raw = await r.get(f"account_categories_by_service_id:{svc.account_service_id}:ru")
            assert raw
            lst = orjson.loads(raw)
            assert lst[0]["account_category_id"] == c3.account_category_id
            assert [it["index"] for it in lst] == [0, 1, 2]

        # перемещение c3 в конец (index 2)
        updated2 = await update_account_category(c3.account_category_id, index=2)
        assert updated2.index == 2

        async with get_db() as session:
            res = await session.execute(select(AccountCategories).where(AccountCategories.account_service_id == svc.account_service_id).order_by(AccountCategories.index.asc()))
            rows = res.scalars().all()
            assert rows[0].index == 0
            assert rows[1].index == 1
            assert rows[2].index == 2
            # последний должен быть c3
            assert rows[2].account_category_id == c3.account_category_id

        async with get_redis() as r:
            raw = await r.get(f"account_categories_by_service_id:{svc.account_service_id}:ru")
            lst = orjson.loads(raw)
            assert [it["index"] for it in lst] == [0, 1, 2]


    @pytest.mark.asyncio
    async def test_update_account_category_validation_and_product_conflict(self, create_account_service, create_account_category, create_product_account):
        from src.services.database.selling_accounts.actions import update_account_category

        svc = await create_account_service(filling_redis=False)
        cat = await create_account_category(
            filling_redis=False,
            account_service_id=svc.account_service_id,
            is_accounts_storage=True,
            language="ru"
        )
        prod = await create_product_account(filling_redis=False, account_category_id=cat.account_category_id)

        # Попытка изменить is_accounts_storage -> должна вызвать ValueError, поскольку is_accounts_storage=True
        with pytest.raises(ValueError):
            await update_account_category(cat.account_category_id, is_accounts_storage=False)

        # Проверка на нормальную цену
        with pytest.raises(ValueError):
            await update_account_category(cat.account_category_id, price_one_account=0)

        with pytest.raises(ValueError):
            await update_account_category(cat.account_category_id, cost_price_one_account=-1)

        updated = await update_account_category(cat.account_category_id, show=False)
        assert updated.show is False

        # Проверка БД
        async with get_db() as session:
            res = await session.execute(
                select(AccountCategories)
                .where(AccountCategories.account_category_id == cat.account_category_id)
            )
            dbcat = res.scalar_one()
            assert dbcat.show is False

        # Redis updated keys should exist (function calls filling... on update)
        async with get_redis() as r:
            raw = await r.get(f"account_categories_by_category_id:{cat.account_category_id}:ru")
            parsed = orjson.loads(raw)
            assert parsed["account_category_id"] == cat.account_category_id
            assert parsed["show"] == False


class TestUpdateAccountCategoryTranslation:
    @pytest.mark.asyncio
    async def test_update_account_category_translation_success(self,create_account_category):
        from src.services.database.selling_accounts.actions import update_account_category_translation

        full_category = await create_account_category(filling_redis=True, language="ru", name="orig", description="orig")

        # обновляем перевод
        new_name = "новое имя"
        new_description = "новое описание"
        updated = await update_account_category_translation(
            account_category_id=full_category.account_category_id,
            language="ru",
            name=new_name,
            description=new_description
        )

        # проверяем, что возвращаемый объект имеет новые поля
        assert updated.name == new_name
        assert updated.description == new_description

        # проверяем в БД
        async with get_db() as session:
            res = await session.execute(
                select(AccountCategoryTranslation).where(
                    (AccountCategoryTranslation.account_category_id == full_category.account_category_id) &
                    (AccountCategoryTranslation.lang == "ru")
                )
            )
            tr = res.scalar_one_or_none()
            assert tr is not None
            assert tr.name == new_name
            assert tr.description == new_description

        # проверяем Redis: ключ отдельного category
        async with get_redis() as r:
            key_single = f"account_categories_by_category_id:{full_category.account_category_id}:ru"
            raw_single = await r.get(key_single)
            assert raw_single is not None, "Ожидается наличие ключа в redis для отдельной категории"
            parsed_single = orjson.loads(raw_single)
            assert parsed_single["name"] == new_name
            assert parsed_single["description"] == new_description

            # key списка категорий по сервису
            key_list = f"account_categories_by_service_id:{full_category.account_service_id}:ru"
            raw_list = await r.get(key_list)
            assert raw_list is not None, "Ожидается наличие ключа списка категорий по сервису"
            parsed_list = orjson.loads(raw_list)
            # среди элементов списка должен быть элемент с нашим id и обновлённым именем
            found = [x for x in parsed_list if x["account_category_id"] == full_category.account_category_id]
            assert found, "В списке категорий по сервису не найден элемент с обновлённой категорией"
            assert found[0]["name"] == new_name


    @pytest.mark.asyncio
    async def test_update_account_category_translation_errors(self, create_account_category):
        from src.services.database.selling_accounts.actions import update_account_category_translation
        # несуществующая категория
        with pytest.raises(ValueError):
            await update_account_category_translation(account_category_id=999999, language="ru", name="x")

        # создаём реальную категорию с переводом "ru"
        full_category = await create_account_category(filling_redis=False, language="ru", name="orig")

        # пытаемся обновить перевод на языке которого нет (например 'en') -> ожидаем ValueError
        with pytest.raises(ValueError):
            await update_account_category_translation(account_category_id=full_category.account_category_id, language="en", name="x")

class TestUpdateAccountStorage:
    @pytest.mark.asyncio
    async def test_update_account_storage_sold_account(self, create_sold_account, create_account_storage):
        from src.services.database.selling_accounts.actions import update_account_storage
        account_storage = await create_account_storage()
        _, full_account = await create_sold_account(
            filling_redis=True, account_storage_id=account_storage.account_storage_id, language="ru"
        )
        sold_account_id = full_account.sold_account_id

        # делаем аккаунт невалидным
        await update_account_storage(account_storage_id=account_storage.account_storage_id, is_active=False)

        async with get_db() as session:
            res_db = await session.execute(select(AccountStorage).where(AccountStorage.account_storage_id == account_storage.account_storage_id))
            account_storage: AccountStorage = res_db.scalar_one()
            assert account_storage.is_active == False

        async with get_redis() as r:
            # в redis не должны ничего хранить, т.к. мы установили is_valid == False
            json_str = await r.get(f"sold_accounts_by_accounts_id:{sold_account_id}:ru")
            assert not json_str

            json_str = await r.get(f"sold_accounts_by_owner_id:{full_account.owner_id}:ru")
            assert not json_str

    @pytest.mark.asyncio
    async def test_update_account_storage_product_account(self, create_product_account, create_account_storage):
        from src.services.database.selling_accounts.actions import update_account_storage
        account_storage = await create_account_storage()
        _, full_account = await create_product_account(filling_redis=True, account_storage_id=account_storage.account_storage_id)
        product_account_id = full_account.account_id

        # делаем аккаунт невалидным
        await update_account_storage(account_storage_id=account_storage.account_storage_id, is_valid=False)

        async with get_db() as session:
            res_db = await session.execute(
                select(AccountStorage).where(AccountStorage.account_storage_id == account_storage.account_storage_id))
            account_storage: AccountStorage = res_db.scalar_one()
            assert account_storage.is_valid == False

        async with get_redis() as r:
            raw_single = await r.get(f"product_accounts_by_account_id:{product_account_id}")
            product_account = ProductAccountFull(**orjson.loads(raw_single))
            assert product_account.account_storage.is_valid == False