from typing import List

from orjson import orjson
from sqlalchemy import select, func

from src.services.database.database import get_db
from src.services.database.filling_database import filling_referral_lvl
from src.services.referrals.models import ReferralLevels, Referrals, IncomeFromReferrals
from src.redis_dependencies.core_redis import get_redis
from src.services.users.models import UserAuditLogs


async def get_all_referrals(user_id) -> List[Referrals]:
    """Вернёт всех рефералов у данного пользователя. Список отсортирован (desc)"""
    async with get_db() as session_db:
        result_db = await session_db.execute(
            select(Referrals)
            .where(Referrals.owner_user_id == user_id)
            .order_by(Referrals.created_at.desc())
        )
        return result_db.scalars().all()


async def get_referral_income_page(user_id: int, page: int = None, page_size: int = 10) -> List[IncomeFromReferrals]:
    """Еслине указывать page, то вернётся весь список"""
    async with get_db() as session_db:
        query = select(
            IncomeFromReferrals
        ).where(IncomeFromReferrals.owner_user_id == user_id).order_by(IncomeFromReferrals.created_at.desc())

        if page:
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)

        result_db = await session_db.execute(query)
        return result_db.scalars().all()

async def get_count_referral_income(user_id: int) -> int:
    async with get_db() as session_db:
        result = await session_db.execute(
            select(func.count()).where(IncomeFromReferrals.owner_user_id == user_id)
        )
        return result.scalar()

async def get_income_from_referral(income_from_referral_id: int) -> IncomeFromReferrals:
    async with get_db() as session_db:
        result = await session_db.execute(
            select(IncomeFromReferrals)
            .where(IncomeFromReferrals.income_from_referral_id == income_from_referral_id)
        )
        return result.scalar_one_or_none()


async def get_referral_lvl()->List[ReferralLevels]:
    """Вернёт ReferralLevels отсортированный по возрастанию level"""
    async with get_redis() as session_redis:
        lvl_redis = await session_redis.get(f'referral_levels')
        if lvl_redis:
            # Десериализуем данные из Redis
            levels_data = orjson.loads(lvl_redis)
            # Создаем список объектов
            list_referrals_lvl = [ReferralLevels(**level) for level in levels_data]

            return sorted(list_referrals_lvl, key=lambda x: x.level)

    async with get_db() as session_db:
        result_db = await session_db.execute(select(ReferralLevels))
        lvl_db = result_db.scalars().all()
        if lvl_db:
            async with get_redis() as session_redis:
                await session_redis.set(f'referral_levels', orjson.dumps([lvl.to_dict() for lvl in lvl_db]))
            return sorted(lvl_db, key=lambda x: x.level)
        else:
            await filling_referral_lvl()
            return await get_referral_lvl()

async def add_referral(referral_id: int, owner_id: int):
    referral_lvls = await get_referral_lvl()
    min_level_obj = min(referral_lvls, key=lambda x: x.level)

    new_ref = Referrals(
        referral_id=referral_id,
        owner_user_id=owner_id,
        level=min_level_obj.level
    )
    new_log_1 = UserAuditLogs(
        user_id = owner_id,
        action_type = 'new_referral',
        details = {
            'message': 'У пользователя новый реферал',
            'referral_id': referral_id,
        }
    )
    new_log_2 = UserAuditLogs(
        user_id=referral_id,
        action_type='became_referral',
        details={
            'message': 'Пользователь стал рефералом',
            'owner_id': owner_id,
        }
    )

    async with get_db() as session_db:
        session_db.add(new_ref)
        session_db.add(new_log_1)
        session_db.add(new_log_2)
        await session_db.commit()

