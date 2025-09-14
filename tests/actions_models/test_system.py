import pytest
from orjson import orjson
from sqlalchemy import delete, select

from src.services.system.models import Settings
from src.services.system.actions import get_settings, update_settings
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import create_settings
from tests.fixtures.helper_functions import comparison_models



@pytest.mark.asyncio
@pytest.mark.parametrize(
    'use_redis',
    [
        True,
        False
    ]
)
async def test_get_settings(use_redis, create_settings):
    if use_redis:
        async with get_redis() as session_redis:
            await session_redis.set(
                f'settings',
                orjson.dumps(create_settings.to_dict())
            )
        async with get_db() as session_db:
            await session_db.execute(delete(Settings))
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()


    selected_settings = await get_settings()

    await comparison_models(create_settings, selected_settings, ['settings_id'])

@pytest.mark.asyncio
async def test_update_settings(create_settings):
    """Проверяем, что update_user меняет данные в БД и Redis"""
    # изменяем данные пользователя
    settings = create_settings
    settings.FAQ = "new FAQ"

    updated_settings = await update_settings(settings) # проверяемый метод

    async with get_db() as session_db:
        settings_db = (await session_db.execute(select(Settings))).scalars().first()

    await comparison_models(settings, settings_db, ['settings_id'])# проверка БД
    await comparison_models(settings, updated_settings, ['settings_id'])# проверка возвращаемого объекта

    # проверка Redis
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"settings")
        assert redis_data is not None
        redis_settings = Settings(**orjson.loads(redis_data))
        await comparison_models(settings, redis_settings, ['settings_id'])# проверка redis


