import pytest
from orjson import orjson
from sqlalchemy import select

from src.exceptions.service_exceptions import TranslationAlreadyExists, ServiceTypeBusy
from src.services.database.selling_accounts.models.models import TgAccountMedia
from src.services.database.system.models import UiImages
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.models import AccountServices, DeletedAccounts, SoldAccounts, \
    AccountCategoryTranslation, ProductAccounts, AccountCategories, SoldAccountsTranslation, AccountStorage


@pytest.mark.asyncio
async def test_add_account_services(replacement_needed_modules, create_type_account_service):
    from src.services.database.selling_accounts.actions import add_account_services
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

    with pytest.raises(ServiceTypeBusy):
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
async def test_add_translation_in_account_category(replacement_needed_modules, create_account_category):
    from src.services.database.selling_accounts.actions import add_translation_in_account_category
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
async def test_add_account_category(replacement_needed_modules, create_account_service):
    from src.services.database.selling_accounts.actions import add_account_category
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

        result = await session_db.execute(
            select(UiImages).where(UiImages.key == category_db.ui_image_key)
        )
        ui_image = result.scalar_one_or_none()
        assert category_db is not None

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
async def test_add_product_account(replacement_needed_modules, create_account_category, create_account_storage):
    from src.services.database.selling_accounts.actions import add_product_account
    # Создаём категорию-хранилище
    account_storage = await create_account_storage()
    category = await create_account_category(is_accounts_storage=True, filling_redis=False)

    # Успешное добавление
    new_product = await add_product_account(
        account_category_id=category.account_category_id,
        account_storage_id=account_storage.account_storage_id,
    )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ProductAccounts).where(ProductAccounts.account_id == new_product.account_id)
        )
        product_db = result.scalar_one_or_none()
        assert product_db is not None

    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"product_accounts_by_account_id:{new_product.account_id}")
        assert redis_data

        redis_data = await session_redis.get(f"product_accounts_by_category_id:{category.account_category_id}")
        assert redis_data

    # Ошибка: категория не является хранилищем
    category_non_storage = await create_account_category(is_accounts_storage=False, filling_redis=False)
    with pytest.raises(ValueError):
        await add_product_account(
            account_category_id=category_non_storage.account_category_id,
            account_storage_id=account_storage.account_storage_id,
        )


@pytest.mark.asyncio
async def test_add_translation_in_sold_account(replacement_needed_modules):
    from src.services.database.selling_accounts.actions import add_account_storage

    new_acc = await add_account_storage(
        type_service_name='telegram',
        checksum='checksum',
        encrypted_key='fgdshjyte3',
        encrypted_key_nonce='encrypted_key_nonce',
        phone_number='+7 324 345-54-34',
    )

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(AccountStorage)
            .where(AccountStorage.account_storage_id == new_acc.account_storage_id)
        )
        account = result_db.scalar_one_or_none()
        assert account is not None

        result_db = await session_db.execute(
            select(TgAccountMedia)
            .where(TgAccountMedia.account_storage_id == new_acc.account_storage_id)
        )
        tg_media = result_db.scalar_one_or_none()
        assert tg_media is not None



@pytest.mark.asyncio
async def test_add_translation_in_sold_account(replacement_needed_modules, create_sold_account):
    from src.services.database.selling_accounts.actions import add_translation_in_sold_account
    sold_account, _ = await create_sold_account(filling_redis=False)

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
        assert account[0]["name"] == "translated name"

        redis_data = await session_redis.get(f"sold_accounts_by_accounts_id:{sold_account.sold_account_id}:en")
        assert redis_data
        account = orjson.loads(redis_data)
        assert account["name"] == "translated name"

    # Ошибка: перевод уже существует
    with pytest.raises(TranslationAlreadyExists):
        await add_translation_in_sold_account(
            sold_account_id=sold_account.sold_account_id,
            language="en",
            name="again",
            description="again"
        )


@pytest.mark.asyncio
async def test_add_sold_account(replacement_needed_modules, create_new_user, create_account_storage, create_type_account_service):
    from src.services.database.selling_accounts.actions import add_sold_account
    user = await create_new_user()
    account_storage = await create_account_storage()
    type_service = await create_type_account_service(filling_redis=False)

    # Успешное добавление
    sold = await add_sold_account(
        owner_id=user.user_id,
        type_account_service_id=type_service.type_account_service_id,
        account_storage_id=account_storage.account_storage_id,
        language="ru",
        name="sold",
        description="sold desc",
    )
    assert sold.owner_id == user.user_id
    assert sold.name == "sold"

    async with get_db() as session_db:
        result = await session_db.execute(
            select(SoldAccounts).where(SoldAccounts.sold_account_id == sold.sold_account_id)
        )
        sold_db: SoldAccounts = result.scalar_one_or_none()
        assert sold_db is not None

    # Ошибка: несуществующий пользователь
    with pytest.raises(ValueError):
        await add_sold_account(
            owner_id=99999,
            type_account_service_id=type_service.type_account_service_id,
            account_storage_id=account_storage.account_storage_id,
            language="ru",
            name="fail",
            description="fail"
        )


@pytest.mark.asyncio
async def test_add_deleted_accounts(replacement_needed_modules, create_account_storage, create_type_account_service):
    from src.services.database.selling_accounts.actions import add_deleted_accounts
    account_storage = await create_account_storage()
    type_service = await create_type_account_service(filling_redis=False)

    deleted = await add_deleted_accounts(
        type_account_service_id=type_service.type_account_service_id,
        account_storage_id=account_storage.account_storage_id,
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
            account_storage_id=account_storage.account_storage_id,
            category_name="fail",
            description="fail"
        )