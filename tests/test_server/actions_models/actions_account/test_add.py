import pytest
from orjson import orjson
from sqlalchemy import select, update

from src.exceptions import TranslationAlreadyExists, TheCategoryStorageAccount, TheCategoryNotStorageAccount
from src.services.database.product_categories.models import TgAccountMedia
from src.services.database.product_categories.models.product_account import AccountServiceType
from src.services.database.system.models import UiImages
from src.services.redis.core_redis import get_redis
from src.services.database.core.database import get_db
from src.services.database.product_categories.models import DeletedAccounts, SoldAccounts, \
    CategoryTranslation, ProductAccounts, Categories, SoldAccountsTranslation, AccountStorage


@pytest.mark.asyncio
async def test_add_translation_in_category(replacement_needed_modules, create_category):
    from src.services.database.product_categories.actions import add_translation_in_category
    category = await create_category(filling_redis=False)

    # Успешное добавление перевода
    translation = await add_translation_in_category(
        category_id=category.category_id,
        language="en",
        name="translated name",
        description="translated description"
    )
    assert translation.category_id == category.category_id
    assert translation.name == "translated name"

    async with get_db() as session_db:
        result = await session_db.execute(
            select(CategoryTranslation).where(
                CategoryTranslation.category_id == category.category_id,
                CategoryTranslation.lang == "en"
            )
        )
        translation_db = result.scalar_one_or_none()
        assert translation_db is not None
        assert translation_db.name == "translated name"

    # Должен закэшироваться в Redis
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(
            f"category:{category.category_id}:en"
        )
        assert redis_data
        category_in_redis: dict = orjson.loads(redis_data)
        assert category_in_redis["category_id"] == category.category_id
        assert category_in_redis["name"] == "translated name"

        redis_data = await session_redis.get(f"main_categories:en")
        assert redis_data
        category_list: list[dict] = orjson.loads(redis_data)
        assert category_list[0]["category_id"] == category.category_id
        assert category_list[0]["name"] == "translated name"


    # Ошибка при повторном добавлении того же языка
    with pytest.raises(ValueError):
        await add_translation_in_category(
            category_id=category.category_id,
            language="en",
            name="duplicated name"
        )

@pytest.mark.asyncio
async def test_add_category(replacement_needed_modules):
    from src.services.database.product_categories.actions import add_category

    # Успешное добавление
    category = await add_category(
        language="ru",
        name="main cat",
        description="desc",
    )
    assert category.is_main is True

    async with get_db() as session_db:
        result = await session_db.execute(
            select(Categories).where(Categories.category_id == category.category_id)
        )
        category_db = result.scalar_one_or_none()
        assert category_db is not None
        assert category_db.index == 0  # первая категория

        result = await session_db.execute(
            select(UiImages).where(UiImages.key == category_db.ui_image_key)
        )
        ui_image = result.scalar_one_or_none()
        assert category_db is not None


@pytest.mark.asyncio
async def test_add_product_account(replacement_needed_modules, create_category, create_account_storage):
    from src.services.database.product_categories.actions import add_product_account
    # Создаём категорию-хранилище
    account_storage = await create_account_storage()
    category = await create_category(is_product_storage=True, filling_redis=False)

    # Успешное добавление
    new_product = await add_product_account(
        type_account_service=AccountServiceType.TELEGRAM,
        category_id=category.category_id,
        account_storage_id=account_storage.account_storage_id,
    )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ProductAccounts).where(ProductAccounts.account_id == new_product.account_id)
        )
        product_db = result.scalar_one_or_none()
        assert product_db is not None

    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"product_account:{new_product.account_id}")
        assert redis_data

        redis_data = await session_redis.get(f"product_accounts_by_category:{category.category_id}")
        assert redis_data

    # Ошибка: категория не является хранилищем
    category_non_storage = await create_category(is_product_storage=False, filling_redis=False)
    with pytest.raises(TheCategoryNotStorageAccount):
        await add_product_account(
            type_account_service=AccountServiceType.TELEGRAM,
            category_id=category_non_storage.category_id,
            account_storage_id=account_storage.account_storage_id,
        )


@pytest.mark.asyncio
async def test_add_translation_in_sold_account(replacement_needed_modules):
    from src.services.database.product_categories.actions import add_account_storage

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
    from src.services.database.product_categories.actions import add_translation_in_sold_account
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

        redis_data = await session_redis.get(f"sold_account:{sold_account.sold_account_id}:en")
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
async def test_add_sold_account(replacement_needed_modules, create_new_user, create_account_storage):
    from src.services.database.product_categories.actions import add_sold_account
    user = await create_new_user()
    account_storage = await create_account_storage()

    # Успешное добавление
    sold = await add_sold_account(
        owner_id=user.user_id,
        type_account_service=AccountServiceType.TELEGRAM,
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
            type_account_service=AccountServiceType.TELEGRAM,
            account_storage_id=account_storage.account_storage_id,
            language="ru",
            name="fail",
            description="fail"
        )


@pytest.mark.asyncio
async def test_add_deleted_accounts(replacement_needed_modules, create_account_storage):
    from src.services.database.product_categories.actions import add_deleted_accounts
    account_storage = await create_account_storage()

    deleted = await add_deleted_accounts(
        type_account_service=AccountServiceType.TELEGRAM,
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
            type_account_service="fake_type_account_service",
            account_storage_id=account_storage.account_storage_id,
            category_name="fail",
            description="fail"
        )