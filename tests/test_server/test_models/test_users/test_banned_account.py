import pytest
from sqlalchemy import select

from src.database.models.users import BannedAccounts
from src.infrastructure.redis import get_redis
from src.models.create_models.users import CreateBannedAccountsDTO


class TestBannedAccountService:

    @pytest.mark.asyncio
    async def test_create_ban_updates_db_and_redis(
        self,
        session_db_fix,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()
        ban_data = CreateBannedAccountsDTO(reason="violated rules")

        ban = await container_fix.banned_account_service.create_ban(
            user_id=user.user_id,
            data=ban_data,
            make_commit=True,
            filling_redis=True,
        )

        assert ban.user_id == user.user_id
        assert ban.reason == ban_data.reason

        query = await session_db_fix.execute(
            select(BannedAccounts).where(BannedAccounts.user_id == user.user_id)
        )
        db_ban = query.scalar_one_or_none()

        assert db_ban is not None
        assert db_ban.reason == ban_data.reason

        redis_reason = await get_redis().get(f"banned_account:{user.user_id}")
        if isinstance(redis_reason, bytes):
            redis_reason = redis_reason.decode()

        assert redis_reason == ban_data.reason

        cached_reason = await container_fix.banned_account_service.get_ban(user.user_id)
        assert cached_reason == ban_data.reason

    @pytest.mark.asyncio
    async def test_delete_ban_cleans_db_and_redis(
        self,
        session_db_fix,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()
        ban_data = CreateBannedAccountsDTO(reason="temporary block")

        await container_fix.banned_account_service.create_ban(
            user_id=user.user_id,
            data=ban_data,
            make_commit=True,
            filling_redis=True,
        )

        await container_fix.banned_account_service.delete_ban(
            user_id=user.user_id,
            make_commit=True,
            filling_redis=True,
        )

        query = await session_db_fix.execute(
            select(BannedAccounts).where(BannedAccounts.user_id == user.user_id)
        )
        assert query.scalar_one_or_none() is None

        assert await get_redis().get(f"banned_account:{user.user_id}") is None
        assert await container_fix.banned_account_service.get_ban(user.user_id) is None
