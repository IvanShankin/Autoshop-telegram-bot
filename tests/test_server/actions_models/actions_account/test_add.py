import pytest
from orjson import orjson
from sqlalchemy import select

from src.redis_dependencies.core_redis import get_redis
from src.services.database.database import get_db
from src.services.selling_accounts.actions import add_account_services, add_deleted_accounts, add_sold_sold_account, \
    add_translation_in_account_category, add_product_account, add_translation_in_sold_account, add_account_category
from src.services.selling_accounts.models import AccountServices, DeletedAccounts, SoldAccounts, \
    AccountCategoryTranslation, ProductAccounts, AccountCategories, SoldAccountsTranslation


@pytest.mark.asyncio
async def test_add_account_services(create_type_account_service):
    type_service = await create_type_account_service(name="telegram")
    type_service_2 = await create_type_account_service(name="other")

    new_service = await add_account_services(
        name="account_service",
        type_account_service_id=type_service.type_account_service_id
    )
    new_service_2 = await add_account_services(
        name="account_service_2",
        type_account_service_id=type_service_2.type_account_service_id
    )

    with pytest.raises(ValueError):
        await add_account_services(name="service_fail", type_account_service_id=type_service.type_account_service_id)

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountServices)
            .where(AccountServices.account_service_id == new_service.account_service_id)
        )
        service_db: AccountServices = result_db.scalar_one_or_none()

        assert new_service.to_dict() == service_db.to_dict()

    async with get_redis() as session_redis:
        result_redis = await session_redis.get('account_services')
        service_list = orjson.loads(result_redis)
        assert new_service.to_dict() in service_list
        assert service_list[0]['index'] == 0
        assert service_list[1]['index'] == 1

        result_redis = await session_redis.get(f"account_service:{new_service.account_service_id}")
        service_from_redis = orjson.loads(result_redis)
        assert new_service.to_dict() == service_from_redis

@pytest.mark.asyncio
async def test_add_translation_in_account_category(create_account_category):
    category = await create_account_category(filling_redis=False)

    # Успешное добавление перевода
    translation = await add_translation_in_account_category(
        account_category_id=category.account_category_id,
        language="en",
        name="translated name",
        description="translated description"
    )
    assert translation.account_category_id == category.account_category_id
    assert translation.name == "translated name"

    async with get_db() as session_db:
        result = await session_db.execute(
            select(AccountCategoryTranslation).where(
                AccountCategoryTranslation.account_category_id == category.account_category_id,
                AccountCategoryTranslation.lang == "en"
            )
        )
        translation_db = result.scalar_one_or_none()
        assert translation_db is not None
        assert translation_db.name == "translated name"

    # Должен закэшироваться в Redis
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(
            f"account_categories_by_category_id:{category.account_category_id}:en"
        )
        assert redis_data
        category_in_redis: dict = orjson.loads(redis_data)
        assert category_in_redis["account_category_id"] == category.account_category_id
        assert category_in_redis["name"] == "translated name"

        redis_data = await session_redis.get(f"account_categories_by_service_id:{category.account_service_id}:en")
        assert redis_data
        category_list: list[dict] = orjson.loads(redis_data)
        assert category_list[0]["account_category_id"] == category.account_category_id
        assert category_list[0]["name"] == "translated name"


    # Ошибка при повторном добавлении того же языка
    with pytest.raises(ValueError):
        await add_translation_in_account_category(
            account_category_id=category.account_category_id,
            language="en",
            name="duplicated name"
        )

@pytest.mark.asyncio
async def test_add_account_category(create_account_service):
    service = await create_account_service(filling_redis=False)

    # Успешное добавление
    category = await add_account_category(
        account_service_id=service.account_service_id,
        language="ru",
        name="main cat",
        description="desc",
        is_accounts_storage=True
    )
    assert category.account_service_id == service.account_service_id
    assert category.is_main is True

    async with get_db() as session_db:
        result = await session_db.execute(
            select(AccountCategories).where(AccountCategories.account_category_id == category.account_category_id)
        )
        category_db = result.scalar_one_or_none()
        assert category_db is not None
        assert category_db.index == 0  # первая категория

    # Ошибка, если указать parent_id от категории-хранилища
    with pytest.raises(ValueError):
        await add_account_category(
            account_service_id=service.account_service_id,
            language="ru",
            name="child cat",
            parent_id=category.account_category_id,
            is_accounts_storage=True
        )


@pytest.mark.asyncio
async def test_add_product_account(create_account_category):
    # Создаём категорию-хранилище
    category = await create_account_category(is_accounts_storage=True, filling_redis=False)

    # Успешное добавление
    new_product = await add_product_account(
        account_category_id=category.account_category_id,
        hash_login="login123",
        hash_password="pass123"
    )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ProductAccounts).where(ProductAccounts.account_id == new_product.account_id)
        )
        product_db = result.scalar_one_or_none()
        assert product_db is not None
        assert product_db.hash_login == "login123"

    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"product_accounts_by_account_id:{new_product.account_id}")
        assert redis_data
        account = orjson.loads(redis_data)
        assert account["hash_login"] == "login123"

        redis_data = await session_redis.get(f"product_accounts_by_category_id:{category.account_category_id}")
        assert redis_data
        account_list = orjson.loads(redis_data)
        assert account_list[0]["hash_login"] == "login123"

    # Ошибка: категория не является хранилищем
    category_non_storage = await create_account_category(is_accounts_storage=False, filling_redis=False)
    with pytest.raises(ValueError):
        await add_product_account(
            account_category_id=category_non_storage.account_category_id,
            hash_login="fail",
            hash_password="fail"
        )


@pytest.mark.asyncio
async def test_add_translation_in_sold_account(create_sold_account):
    sold_account = await create_sold_account(filling_redis=False)

    # Успешное добавление нового перевода
    translated = await add_translation_in_sold_account(
        sold_account_id=sold_account.sold_account_id,
        language="en",
        name="translated name",
        description="translated description"
    )
    assert translated.sold_account_id == sold_account.sold_account_id
    assert translated.name == "translated name"

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(SoldAccountsTranslation)
            .where(
                (SoldAccountsTranslation.sold_account_id == sold_account.sold_account_id) &
                (SoldAccountsTranslation.lang == 'en')
            )
        )
        sold_account_translation: SoldAccountsTranslation = result_db.scalar_one_or_none()
        assert sold_account_translation.name == "translated name"

    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"sold_accounts_by_owner_id:{sold_account.owner_id}:en")
        assert redis_data
        account = orjson.loads(redis_data)
        assert account[1]["name"] == "translated name" # берём первый [1] т.к. в тестируемой функции вызывается заполнение redis

        redis_data = await session_redis.get(f"sold_accounts_by_accounts_id:{sold_account.sold_account_id}:en")
        assert redis_data
        account = orjson.loads(redis_data)
        assert account["name"] == "translated name"

    # Ошибка: перевод уже существует
    with pytest.raises(ValueError):
        await add_translation_in_sold_account(
            sold_account_id=sold_account.sold_account_id,
            language="en",
            name="again",
            description="again"
        )


@pytest.mark.asyncio
async def test_add_sold_sold_account(create_new_user, create_type_account_service):
    user = await create_new_user()
    type_service = await create_type_account_service(filling_redis=False)

    # Успешное добавление
    sold = await add_sold_sold_account(
        owner_id=user.user_id,
        type_account_service_id=type_service.type_account_service_id,
        is_valid=True,
        is_deleted=False,
        language="ru",
        name="sold",
        description="sold desc",
        hash_login="hash_login",
        hash_password="hash_password",
    )
    assert sold.owner_id == user.user_id
    assert sold.name == "sold"

    async with get_db() as session_db:
        result = await session_db.execute(
            select(SoldAccounts).where(SoldAccounts.sold_account_id == sold.sold_account_id)
        )
        sold_db = result.scalar_one_or_none()
        assert sold_db is not None
        assert sold_db.hash_login == "hash_login"

    # Ошибка: несуществующий пользователь
    with pytest.raises(ValueError):
        await add_sold_sold_account(
            owner_id=99999,
            type_account_service_id=type_service.type_account_service_id,
            is_valid=True,
            is_deleted=False,
            language="ru",
            name="fail",
            description="fail"
        )


@pytest.mark.asyncio
async def test_add_deleted_accounts(create_type_account_service):
    type_service = await create_type_account_service(filling_redis=False)

    deleted = await add_deleted_accounts(
        type_account_service_id=type_service.type_account_service_id,
        category_name="cat",
        description="desc"
    )
    assert deleted.category_name == "cat"

    async with get_db() as session_db:
        result = await session_db.execute(
            select(DeletedAccounts).where(DeletedAccounts.deleted_account_id == deleted.deleted_account_id)
        )
        deleted_db = result.scalar_one_or_none()
        assert deleted_db is not None
        assert deleted_db.category_name == "cat"

    # Ошибка при несуществующем типе
    with pytest.raises(ValueError):
        await add_deleted_accounts(
            type_account_service_id=99999,
            category_name="fail",
            description="fail"
        )