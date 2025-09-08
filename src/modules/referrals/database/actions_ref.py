from typing import List

from orjson import orjson
from sqlalchemy import select

from src.database.database import get_db
from src.database.filling_database import filling_referral_lvl
from src.modules.referrals.database.models_ref import ReferralLevels
from src.redis_dependencies.core_redis import get_redis


async def get_referral_lvl()->List[ReferralLevels] | None:
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