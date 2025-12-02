from typing import List, Optional

from orjson import orjson
from sqlalchemy import select, update, delete

from src.exceptions.service_exceptions import InvalidAmountOfAchievement, InvalidSelectedLevel
from src.services.database.core.database import get_db
from src.services.database.core.filling_database import filling_referral_lvl as filling_referral_lvl_in_db
from src.services.database.referrals.models import ReferralLevels, Referrals
from src.services.database.users.models import Users
from src.services.redis.core_redis import get_redis
from src.services.redis.filling_redis import filling_referral_levels


async def get_referral_lvl() -> List[ReferralLevels]:
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
            await filling_referral_lvl_in_db()
            return await get_referral_lvl()


async def add_referral_lvl(amount_of_achievement: int, percent: float) -> ReferralLevels:
    """
    Уровень присвоится следующий от максимального (+ 1)
    :param amount_of_achievement: Сумма с которой достигается уровень
    :param percent: процент начисления владельцу реферала
    :except InvalidAmountOfAchievement: При некорректном ``amount_of_achievement``
    """
    ref_lvls = await get_referral_lvl()
    last_lvl = ref_lvls[-1]
    if amount_of_achievement <= last_lvl.amount_of_achievement:
        raise InvalidAmountOfAchievement(amount_of_achievement_previous_lvl=last_lvl.amount_of_achievement)

    new_ref_lvl = ReferralLevels(
        level=last_lvl.level + 1,
        amount_of_achievement=amount_of_achievement,
        percent=percent
    )
    async with (get_db() as session_db):
        session_db.add(new_ref_lvl)
        await session_db.flush()

        # обновление уровня у пользователей
        subquery = (
            select(Users.user_id)
            .where(Users.total_sum_replenishment >= amount_of_achievement)
        )

        await session_db.execute(
            update(Referrals)
            .where(Referrals.referral_id.in_(subquery))
            .values(level=new_ref_lvl.level)
        )
        await session_db.commit()

    await filling_referral_levels()
    return new_ref_lvl


async def update_referral_lvl(
    ref_lvl_id: int,
    amount_of_achievement: Optional[int] = None,
    percent: Optional[float] = None
) -> ReferralLevels | None:
    """
    :param ref_lvl_id: ID
    :param amount_of_achievement: Сумма с которой достигается уровень. Должна быть не меньше или равным прошлому уровню и не больше или равным следующему уровню
    :param percent: процент начисления владельцу реферала
    :except InvalidAmountOfAchievement: При некорректном ``amount_of_achievement``
    :except InvalidSelectedLevel: При попытке изменить ``amount_of_achievement`` у первого уровня
    """
    update_value = {}
    previous_lvl: ReferralLevels = None
    next_lvl: ReferralLevels = None

    if amount_of_achievement:
        update_value["amount_of_achievement"] = amount_of_achievement
    if percent:
        update_value["percent"] = percent

    if update_value:
        async with get_db() as session_db:
            result_db = await session_db.execute(
                select(ReferralLevels)
                .where(ReferralLevels.referral_level_id == ref_lvl_id)
            )
            current_ref_lvl: ReferralLevels = result_db.scalar_one_or_none()

            if current_ref_lvl.level == 1 and amount_of_achievement is not None:
                raise InvalidSelectedLevel()

            # проверка на корректный amount_of_achievement
            if amount_of_achievement:
                ref_lvls = await get_referral_lvl()
                for lvl in ref_lvls:
                    if current_ref_lvl.level - 1 == lvl.level:
                        previous_lvl = lvl
                    if current_ref_lvl.level + 1 == lvl.level:
                        previous_lvl = lvl

                if (previous_lvl and amount_of_achievement <= previous_lvl.amount_of_achievement or
                    next_lvl and amount_of_achievement >= next_lvl.amount_of_achievement):
                    raise InvalidAmountOfAchievement(
                        amount_of_achievement_previous_lvl=previous_lvl.amount_of_achievement if previous_lvl else None,
                        amount_of_achievement_next_lvl=next_lvl.amount_of_achievement if next_lvl else None
                    )

            result_db = await session_db.execute(
                update(ReferralLevels)
                .where(ReferralLevels.referral_level_id == ref_lvl_id)
                .values(**update_value)
                .returning(ReferralLevels)
            )
            ref_lvl = result_db.scalar_one_or_none()
            await session_db.commit()

            # если пользователь изменил необходимую сумму для уровня и есть уровень меньше изменяемого
            if amount_of_achievement and previous_lvl:
                # обновление уровня у пользователя
                subquery = (
                    select(Users.user_id)
                    .where(Users.total_sum_replenishment < amount_of_achievement)
                )

                await session_db.execute(
                    update(Referrals)
                    .where(Referrals.referral_id.in_(subquery))
                    .values(level=previous_lvl.level)
                )
                await session_db.commit()

        await filling_referral_levels()
        return ref_lvl

    return None


async def delete_referral_lvl(ref_lvl_id: int):
    async with get_db() as session_db:
        await session_db.execute(delete(ReferralLevels).where(ReferralLevels.referral_level_id == ref_lvl_id))
        await session_db.commit()

    await filling_referral_levels()