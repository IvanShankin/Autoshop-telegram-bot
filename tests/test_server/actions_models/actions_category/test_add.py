import pytest
from orjson import orjson
from sqlalchemy import select
from src.services.database.categories.models import CategoryTranslation,  Categories
from src.services.database.core.database import get_db
from src.services.database.system.models import UiImages
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_add_translation_in_category(replacement_needed_modules, create_category):
    from src.services.database.categories.actions import add_translation_in_category
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
    from src.services.database.categories.actions import add_category

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
