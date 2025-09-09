import pytest
from orjson import orjson
from sqlalchemy import delete, select

from src.database.action_main_models import get_user, update_user, get_settings, update_settings
from src.database.models_main import Users, Settings, NotificationSettings
from src.database.database import get_db
from src.modules.referrals.database.actions_ref import get_referral_lvl
from src.modules.referrals.database.models_ref import ReferralLevels
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import create_new_user, create_settings
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'use_redis',
    [
        True,
        False
    ]
)
async def test_get_user(use_redis, create_new_user):
    if use_redis:
        async with get_redis() as session_redis:
            await session_redis.set(
                f'user:{create_new_user.user_id}',
                orjson.dumps(create_new_user.to_dict())
            )
        async with get_db() as session_db:
            await session_db.execute(delete(NotificationSettings).where(NotificationSettings.user_id == create_new_user.user_id))
            await session_db.execute(delete(Users).where(Users.user_id == create_new_user.user_id))
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()


    selected_user = await get_user(create_new_user.user_id)

    assert isinstance(selected_user, Users)
    assert selected_user.user_id == create_new_user.user_id
    assert selected_user.username == create_new_user.username
    assert selected_user.unique_referral_code == create_new_user.unique_referral_code
    assert selected_user.balance == create_new_user.balance
    assert selected_user.total_sum_replenishment == create_new_user.total_sum_replenishment
    assert selected_user.total_profit_from_referrals == create_new_user.total_profit_from_referrals
    # created_at проверяем с допуском
    assert abs(
        (selected_user.created_at - create_new_user.created_at).total_seconds()
    ) < 2

@pytest.mark.asyncio
async def test_update_user(create_new_user):
    """Проверяем, что update_user меняет данные в БД и Redis"""
    # изменяем данные пользователя
    create_new_user.username = "updated_username"
    create_new_user.balance = 500
    create_new_user.total_profit_from_referrals = 50

    updated_user = await update_user(create_new_user)

    async with get_db() as session_db:
        db_user = await session_db.get(Users, create_new_user.user_id)

    # проверка БД
    assert db_user.username == "updated_username"
    assert db_user.balance == 500
    assert db_user.total_profit_from_referrals == 50

    # проверка возвращаемого объекта
    assert isinstance(updated_user, Users)
    assert updated_user.username == db_user.username
    assert updated_user.balance == db_user.balance
    assert updated_user.total_profit_from_referrals == db_user.total_profit_from_referrals

    # проверка Redis
    async with get_redis() as session_redis:
        redis_data = await session_redis.get(f"user:{create_new_user.user_id}")
        assert redis_data is not None
        redis_user = Users(**parse_redis_user(redis_data))
        assert redis_user.username == "updated_username"
        assert redis_user.balance == 500
        assert redis_user.total_profit_from_referrals == 50


@pytest.mark.asyncio
@pytest.mark.parametrize("use_redis", [True, False])
async def test_get_referral_lvl(use_redis):
    """Проверяем, что get_referral_lvl корректно работает и с Redis, и с БД"""
    if use_redis:
        async with get_db() as session_db:
            await session_db.execute(delete(ReferralLevels))
            await session_db.commit()

        lvl = ReferralLevels(level=1, amount_of_achievement=100, percent=10)

        async with get_redis() as session_redis:
            await session_redis.set(
                "referral_levels",
                orjson.dumps([lvl.to_dict()]),
            )
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()

        async with get_db() as session_db:
            lvl = ReferralLevels(level=2, amount_of_achievement=200, percent=20)
            session_db.add(lvl)
            await session_db.commit()
            await session_db.refresh(lvl)

    levels = await get_referral_lvl()

    assert levels is not None
    assert isinstance(levels, list)
    assert all(isinstance(l, ReferralLevels) for l in levels)
    assert levels == sorted(levels, key=lambda x: x.level)


# --- Helpers ---

def parse_redis_user(redis_bytes: bytes) -> dict:
    """Десериализация user из Redis с конвертацией даты"""
    import orjson
    from dateutil.parser import parse

    data = orjson.loads(redis_bytes)
    if "created_at" in data and isinstance(data["created_at"], str):
        data["created_at"] = parse(data["created_at"])
    return data


