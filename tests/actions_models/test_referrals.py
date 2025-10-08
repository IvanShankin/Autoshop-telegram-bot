import pytest

from orjson import orjson
from sqlalchemy import delete, select

from src.services.database.database import get_db
from src.services.referrals.actions.actions_ref import add_referral
from src.services.referrals.models import ReferralLevels, Referrals
from src.services.referrals.actions import get_referral_lvl
from src.redis_dependencies.core_redis import get_redis
from src.services.users.models import UserAuditLogs


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

@pytest.mark.asyncio
async def test_get_referral_lvl(create_new_user):
    user = await create_new_user()
    owner = await create_new_user()

    await add_referral(user.user_id, owner.user_id)

    async with get_db() as session_db:
        result_db = await session_db.execute(select(Referrals).where(Referrals.referral_id == user.user_id))
        referral: Referrals = result_db.scalar_one_or_none()

        assert referral.referral_id == user.user_id
        assert referral.owner_user_id == owner.user_id

        result_db = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id))
        log = result_db.scalars().all()
        assert len(log) == 1

        result_db = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == owner.user_id))
        log = result_db.scalars().all()
        assert len(log) == 1

