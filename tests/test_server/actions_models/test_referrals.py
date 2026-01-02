from typing import List

import pytest

from orjson import orjson
from sqlalchemy import delete, select

from src.exceptions import InvalidAmountOfAchievement, InvalidSelectedLevel
from src.services.database.core.database import get_db
from src.services.database.referrals.actions import add_referral, get_all_referrals, get_income_from_referral, \
    get_referral_income_page, get_count_referral_income, add_referral_lvl, delete_referral_lvl, update_referral_lvl
from src.services.database.referrals.models import ReferralLevels, Referrals
from src.services.database.referrals.actions import get_referral_lvl
from src.services.redis.core_redis import get_redis
from src.services.database.users.models import UserAuditLogs, Users


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


@pytest.mark.asyncio
async def test_all_get_referrals(create_referral, create_new_user):
    owner = await create_new_user()
    ref_1, _, _ = await create_referral(owner.user_id)
    ref_2, _, _ = await create_referral(owner.user_id)
    ref_3, _, _ = await create_referral(owner.user_id)

    all_ref = await get_all_referrals(owner.user_id)

    assert all_ref[0].to_dict() == ref_3.to_dict()
    assert all_ref[1].to_dict() == ref_2.to_dict()
    assert all_ref[2].to_dict() == ref_1.to_dict()


@pytest.mark.asyncio
async def test_get_referral_income_page(create_new_user, create_income_from_referral):
    owner = await create_new_user()
    income_1, _, _ = await create_income_from_referral(owner_id=owner.user_id)
    income_2, _, _ = await create_income_from_referral(owner_id=owner.user_id)
    income_3, _, _ = await create_income_from_referral(owner_id=owner.user_id)

    all_incomes = await get_referral_income_page(owner.user_id, 1)

    assert all_incomes[0].to_dict() == income_3.to_dict()
    assert all_incomes[1].to_dict() == income_2.to_dict()
    assert all_incomes[2].to_dict() == income_1.to_dict()


@pytest.mark.asyncio
async def test_get_count_referral_income(create_new_user, create_income_from_referral):
    owner = await create_new_user()
    income_1, _, _ = await create_income_from_referral(owner_id=owner.user_id)
    income_2, _, _ = await create_income_from_referral(owner_id=owner.user_id)

    count_income = await get_count_referral_income(owner.user_id)

    assert count_income == 2


@pytest.mark.asyncio
async def test_get_income_from_referral(create_income_from_referral):
    income, _, _ = await create_income_from_referral()
    all_incomes = await get_income_from_referral(income.income_from_referral_id)
    assert all_incomes.to_dict() == income.to_dict()


async def delete_all_ref_lvls_and_create_first(amount_of_achievement: int = 0, percent: float = 0) -> ReferralLevels:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(ReferralLevels.referral_level_id))
        ref_lvls_ids = result_db.scalars().all()
        for ref_lvl_id in ref_lvls_ids: await delete_referral_lvl(ref_lvl_id)

        new_ref_lvl = ReferralLevels(level=1, amount_of_achievement=amount_of_achievement, percent=percent,)
        session_db.add(new_ref_lvl)
        await session_db.commit()
        await session_db.flush()
        return new_ref_lvl


@pytest.mark.asyncio
async def test_add_referral_lvl(create_new_user, create_referral):
    referral_user = await create_new_user(total_sum_replenishment=10000)
    await create_referral(referral_id=referral_user.user_id)

    await delete_all_ref_lvls_and_create_first()

    new_lvl = await add_referral_lvl(amount_of_achievement=9000, percent=10)

    async with get_db() as session_db:
        result_db = await session_db.execute(select(Referrals).where(Referrals.referral_id == referral_user.user_id))
        referral: Referrals = result_db.scalar_one_or_none()

        assert referral.level == new_lvl.level


@pytest.mark.asyncio
async def test_update_referral_lvl(create_new_user, create_referral):
    await delete_all_ref_lvls_and_create_first()

    lvls: List[ReferralLevels] = []
    for i in range(5):
        lvls.append(await add_referral_lvl(amount_of_achievement= i + 1 * 1000, percent= i ))

    referral_user = await create_new_user(total_sum_replenishment=4300)
    await create_referral(referral_id=referral_user.user_id)

    await update_referral_lvl(ref_lvl_id=lvls[4].referral_level_id, amount_of_achievement=4600, percent=20)

    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(ReferralLevels)
            .where(ReferralLevels.referral_level_id == lvls[4].referral_level_id)
        )
        lvl: ReferralLevels = result_db.scalar_one_or_none()
        assert lvl.amount_of_achievement == 4600
        assert lvl.percent == 20

        # проверяем что пользователю обновили уровень до необходимого
        result_db = await session_db.execute(
            select(Referrals)
            .where(Referrals.referral_id == referral_user.user_id)
        )
        referral: Referrals = result_db.scalar_one_or_none()
        assert referral.level == lvls[3].level


@pytest.mark.asyncio
async def test_update_referral_lvl_invalid_amount(create_new_user, create_referral):
    await delete_all_ref_lvls_and_create_first(amount_of_achievement=1000)
    lvl = await add_referral_lvl(amount_of_achievement= 2000, percent=10)

    with pytest.raises(InvalidAmountOfAchievement):
        await update_referral_lvl(ref_lvl_id=lvl.referral_level_id, amount_of_achievement=600, percent=20)


@pytest.mark.asyncio
async def test_update_referral_lvl_invalid_lvl(create_new_user, create_referral):
    lvl = await delete_all_ref_lvls_and_create_first(amount_of_achievement=0)

    with pytest.raises(InvalidSelectedLevel):
        await update_referral_lvl(ref_lvl_id=lvl.referral_level_id, amount_of_achievement=600, percent=20)
