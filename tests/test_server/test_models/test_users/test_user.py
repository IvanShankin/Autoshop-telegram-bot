import orjson
import pytest
from sqlalchemy import select

from src.database.models.users import Users, NotificationSettings
from src.infrastructure.redis import get_redis
from src.models.create_models.users import CreateUserDTO
from src.models.update_models import UpdateUserDTO
from tests.helpers.helper_functions import comparison_models


class TestUserService:

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        'use_redis',
        [
            True,
            False
        ]
    )
    async def test_get_user(self, container_fix, use_redis, create_new_user):
        user = await create_new_user(filling_redis=use_redis)
        selected_user = await container_fix.user_service.get_user(user.user_id)
        assert comparison_models(user, selected_user)

    async def test_get_user_by_ref_code(self, container_fix, create_new_user):
        new_user = await create_new_user()
        returned_user = await container_fix.user_service.get_user_by_ref_code(new_user.unique_referral_code)
        assert comparison_models(new_user, returned_user)

    @pytest.mark.asyncio
    async def test_update_user(self, session_db_fix, container_fix, create_new_user):
        """Проверяем, что update_user меняет данные в БД и Redis"""
        user = await create_new_user()

        updated_user = await container_fix.user_service.update_user(
            user_id=user.user_id,
            data=UpdateUserDTO(
                username="updated_username",
                balance=500,
                total_profit_from_referrals=50,
            ),
            make_commit=True,
            filling_redis=True
        )

        result_db = await session_db_fix.execute(select(Users).where(Users.user_id == user.user_id))
        db_user = result_db.scalar_one_or_none()

        comparison_models(updated_user, db_user)

        # проверка Redis
        session_redis = get_redis()
        redis_data = await session_redis.get(f"user:{user.user_id}")
        assert redis_data is not None
        comparison_models(updated_user, orjson.loads(redis_data))

    @pytest.mark.asyncio
    async def test_create_new_user(
        self,
        session_db_fix,
        container_fix,
    ):
        """Проверяет создание пользователя, уведомлений, логов и запись в Redis"""

        new_user = await container_fix.user_service.create_user(
            data=CreateUserDTO(
                user_id=101,
                username="test_user",
            )
        )

        result_user = await session_db_fix.execute(select(Users).where(Users.user_id == new_user.user_id))
        user = result_user.scalar_one()
        assert comparison_models(new_user, user)

        result_notif = await session_db_fix.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == new_user.user_id)
        )
        notif = result_notif.scalar_one()
        assert notif.user_id == new_user.user_id

        # Проверяем Redis
        session_redis = get_redis()

        data = await session_redis.get(f"user:{new_user.user_id}")
        assert data is not None
        assert comparison_models(new_user, data)

        data = await session_redis.get(f"subscription_prompt:{new_user.user_id}")
        assert data