import pytest
from orjson import orjson
from sqlalchemy import delete

from tests.fixtures.helper_functions import parse_redis_user
from src.services.users.models import Users, NotificationSettings
from src.services.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import create_new_user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'use_redis',
    [
        True,
        False
    ]
)
async def test_get_user(use_redis, create_new_user):
    from src.services.users.actions import get_user
    user = await create_new_user()
    if use_redis:
        async with get_redis() as session_redis:
            await session_redis.set(
                f'user:{user.user_id}',
                orjson.dumps(user.to_dict())
            )
        async with get_db() as session_db:
            await session_db.execute(delete(NotificationSettings).where(NotificationSettings.user_id == user.user_id))
            await session_db.execute(delete(Users).where(Users.user_id == user.user_id))
    else:
        async with get_redis() as session_redis:
            await session_redis.flushdb()


    selected_user = await get_user(user.user_id)

    assert isinstance(selected_user, Users)
    assert selected_user.user_id == user.user_id
    assert selected_user.username == user.username
    assert selected_user.unique_referral_code == user.unique_referral_code
    assert selected_user.balance == user.balance
    assert selected_user.total_sum_replenishment == user.total_sum_replenishment
    assert selected_user.total_profit_from_referrals == user.total_profit_from_referrals
    # created_at проверяем с допуском
    assert abs((selected_user.created_at - user.created_at).total_seconds()) < 2

@pytest.mark.asyncio
async def test_update_user(create_new_user):
    """Проверяем, что update_user меняет данные в БД и Redis"""
    from src.services.users.actions import update_user
    # изменяем данные пользователя
    user = await create_new_user()
    user.username = "updated_username"
    user.balance = 500
    user.total_profit_from_referrals = 50

    updated_user = await update_user(user)

    async with get_db() as session_db:
        db_user = await session_db.get(Users, user.user_id)

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
        redis_data = await session_redis.get(f"user:{user.user_id}")
        assert redis_data is not None
        redis_user = Users(**parse_redis_user(redis_data))
        assert redis_user.username == "updated_username"
        assert redis_user.balance == 500
        assert redis_user.total_profit_from_referrals == 50

