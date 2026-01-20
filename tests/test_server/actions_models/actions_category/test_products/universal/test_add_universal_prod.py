import pytest
import orjson
from sqlalchemy import select

from src.services.database.categories.models.product_universal import (
    UniversalStorage,
    UniversalStorageTranslation,
    ProductUniversal,
    SoldUniversal, UniversalMediaType,
)
from src.services.database.core.database import get_db
from src.services.redis.core_redis import get_redis

from src.exceptions import TranslationAlreadyExists, UserNotFound
from src.exceptions.domain import UniversalStorageNotFound


@pytest.mark.asyncio
async def test_add_universal_storage(create_category):
    from src.services.database.categories.actions import add_universal_storage

    await create_category(filling_redis=False)

    pydantic = await add_universal_storage(
        name="test name",
        language="ru",
        file_path=None,
        encrypted_description="enc_desc",
        encrypted_description_nonce="enc_nonce",
        encrypted_key="enc_key",
        encrypted_key_nonce="enc_key_nonce",
        checksum="chk",
        media_type=UniversalMediaType.DOCUMENT,
    )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(UniversalStorage).where(UniversalStorage.universal_storage_id == pydantic.universal_storage_id)
        )
        storage_db = result.scalar_one_or_none()
        assert storage_db is not None

        result = await session_db.execute(
            select(UniversalStorageTranslation)
            .where(
                (UniversalStorageTranslation.universal_storage_id == pydantic.universal_storage_id) &
                (UniversalStorageTranslation.lang == "ru")
            )
        )
        trans = result.scalar_one_or_none()
        assert trans is not None
        assert trans.name == "test name"

    assert pydantic.name == "test name"
    assert pydantic.universal_storage_id == storage_db.universal_storage_id


@pytest.mark.asyncio
async def test_add_translate_in_universal_storage(create_universal_storage):
    from src.services.database.categories.actions import add_translate_in_universal_storage

    # create storage with default 'ru' translation
    storage, _ = await create_universal_storage()

    translated = await add_translate_in_universal_storage(
        universal_storage_id=storage.universal_storage_id,
        language="en",
        name="name_en",
        encrypted_description="enc_desc_en",
        encrypted_description_nonce="enc_nonce_en",
        filling_redis=False,
    )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(UniversalStorageTranslation)
            .where(
                (UniversalStorageTranslation.universal_storage_id == storage.universal_storage_id) &
                (UniversalStorageTranslation.lang == "en")
            )
        )
        tr = result.scalar_one_or_none()
        assert tr is not None
        assert tr.name == "name_en"

    assert translated.name == "name_en"

    with pytest.raises(TranslationAlreadyExists):
        await add_translate_in_universal_storage(
            universal_storage_id=storage.universal_storage_id,
            language="en",
            name="again",
            encrypted_description=None,
            encrypted_description_nonce=None,
            filling_redis=False,
        )


@pytest.mark.asyncio
async def test_add_product_universal(create_category, create_universal_storage):
    from src.services.database.categories.actions import add_product_universal
    from src.services.database.categories.actions import get_categories_by_category_id

    category = await create_category(is_product_storage=True)
    storage, pyd = await create_universal_storage()

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ProductUniversal).where(ProductUniversal.universal_storage_id == storage.universal_storage_id)
        )
        assert result.scalar_one_or_none() is None

    await add_product_universal(
        universal_storage_id=storage.universal_storage_id,
        category_id=category.category_id,
    )

    async with get_db() as session_db:
        result = await session_db.execute(
            select(ProductUniversal).where(ProductUniversal.universal_storage_id == storage.universal_storage_id)
        )
        product_db = result.scalar_one_or_none()
        assert product_db is not None

    async with get_redis() as session_redis:
        key_by_cat = f"product_universal_by_category:{category.category_id}"
        val_cat = await session_redis.get(key_by_cat)
        assert val_cat is not None, f"missing redis key {key_by_cat}"

        key_single = f"product_universal:{product_db.product_universal_id}"
        val_single = await session_redis.get(key_single)
        assert val_single is not None, f"missing redis key {key_single}"

        # тут данные с redis
        cat = await get_categories_by_category_id(category.category_id)
        assert cat.quantity_product == 1


@pytest.mark.asyncio
async def test_add_sold_universal(create_new_user, create_universal_storage):
    from src.services.database.categories.actions import add_sold_universal

    user = await create_new_user()
    storage, pyd = await create_universal_storage()

    # Call
    await add_sold_universal(owner_id=user.user_id, universal_storage_id=storage.universal_storage_id)

    # DB assert
    async with get_db() as session_db:
        result = await session_db.execute(
            select(SoldUniversal).where(SoldUniversal.universal_storage_id == storage.universal_storage_id)
        )
        sold_db = result.scalar_one_or_none()
        assert sold_db is not None

    # Redis assert: by owner list + single sold item
    async with get_redis() as session_redis:
        key_list = f"sold_universal_by_owner_id:{user.user_id}:ru"
        val_list = await session_redis.get(key_list)
        assert val_list is not None, f"missing redis key {key_list}"
        items = orjson.loads(val_list)
        assert any(item["universal_storage_id"] == storage.universal_storage_id for item in items)

        key_single = f"sold_universal:{sold_db.sold_universal_id}:ru"
        val_single = await session_redis.get(key_single)
        assert val_single is not None, f"missing redis key {key_single}"
        single = orjson.loads(val_single)
        assert single["universal_storage"]["universal_storage_id"] == storage.universal_storage_id


@pytest.mark.asyncio
async def test_add_sold_universal_errors(create_new_user, create_universal_storage):
    from src.services.database.categories.actions import add_sold_universal

    # non-existing user -> expect UserNotFound
    with pytest.raises(UserNotFound):
        await add_sold_universal(owner_id=9999999, universal_storage_id=1)

    user = await create_new_user()
    with pytest.raises(UniversalStorageNotFound):
        await add_sold_universal(owner_id=user.user_id, universal_storage_id=9999999)
