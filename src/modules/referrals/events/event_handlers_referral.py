import orjson
from sqlalchemy import select, desc, update
from sqlalchemy.ext.horizontal_shard import set_shard_id

from src.database.core_models import Users
from src.database.database import get_db
from src.database.events.events_this_modul.schemas import NewReplenishment
from src.modules.referrals.events.schemas import NewIncomeFromRef
from src.modules.referrals.models import ReferralLevels, Referrals, IncomeFromReferrals
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.filling_redis import filling_referral_levels
from src.redis_dependencies.time_storage import TIME_USER


async def referral_event_handler(event):
    if isinstance(event, NewIncomeFromRef):
        await handler_new_income_referral(event)

async def handler_new_income_referral(new_replenishment: NewIncomeFromRef):
    """Сюда попадаем если владелец у реферала точно есть"""
    total_sum_replenishment = new_replenishment.amount
    original_referral_level = 0
    new_level = 0
    percentage = 0

    async with get_redis() as session_redis:
        referral_redis = orjson.loads(await session_redis.get(f'user:{new_replenishment.referral_id}'))

    if referral_redis:
        total_sum_replenishment = referral_redis['total_sum_replenishment']
    else:
        async with get_db() as session_db:
            result_db = await session_db.execute(select(Users).where(Users.user_id == new_replenishment.referral_id))
            referral = result_db.scalar_one_or_none()
            total_sum_replenishment = referral.total_sum_replenishment


    # узнаём уровень у реферала
    async with get_redis() as session_redis:
        referral_levels_redis = orjson.loads(await session_redis.get(f'referral_levels'))

    if referral_levels_redis:
        for level in referral_levels_redis:
            # если сумма пользователя больше или равна требуемой для уровня
            if new_replenishment.balance_before_repl >= level['amount_of_achievement']:
                # выбираем наибольший уровень, который доступен
                if level['level'] > new_level:
                    new_level = level['level']

    else:
        await filling_referral_levels()

        async with get_db() as session_db:
            # Берём все уровни, упорядоченные по level DESC, чтобы сразу найти максимальный, доступный пользователю
            result_db = await session_db.execute(select(ReferralLevels).order_by(desc(ReferralLevels.level)))
            referral_levels_db = result_db.scalars().all()

        for level in referral_levels_db:
            if new_replenishment.balance_before_repl >= level.amount_of_achievement:
                new_level = level.level
                break

    # обновление уровня
    if new_level:
        async with get_db() as session_db:
            await session_db.execute(
                update(Referrals)
                .where(Referrals.referral_id == new_replenishment.referral_id)
                .values(level=new_level)
            )
            await session_db.commit()




    # Сначала ищем процент в Redis
    if referral_levels_redis:
        for level in referral_levels_redis:
            if new_level == level['level']:
                percentage = level['percent']
                break
    else:
        # Если Redis пустой, берём из БД
        async with get_db() as session_db:
            result_db = await session_db.execute(
                select(ReferralLevels).where(ReferralLevels.level == new_level)
            )
            level_db = result_db.scalar_one_or_none()
            if level_db:
                percentage = level_db.percent

    income_amount = int(new_replenishment.amount * percentage / 100)

    async with get_redis() as session_redis:
        user_key = f'user:{new_replenishment.referral_id}'
        referral_redis = await session_redis.get(user_key)
        if referral_redis:
            referral_data = orjson.loads(referral_redis)
            referral_data['total_profit_replenishment'] = referral_data['total_profit_replenishment'] + new_replenishment.amount
            await session_redis.set(user_key, orjson.dumps(referral_data))
        else:
            # Если в Redis нет — обновляем в БД
            async with get_db() as session_db:
                await session_db.execute(
                    update(Users)
                    .where(Users.user_id == new_replenishment.referral_id)
                    .values(
                        total_sum_replenishment=Users.total_sum_replenishment + new_replenishment.amount,
                        level=new_level
                    )
                )
                await session_db.commit()

    # --- Создаём запись о доходе ---
    async with get_db() as session_db:
        new_income = IncomeFromReferrals(
            replenishment_id=new_replenishment.replenishment_id,
            owner_user_id=new_replenishment.owner_id,
            referral_id=new_replenishment.referral_id,
            amount=income_amount,
            percentage_of_replenishment=percentage,
        )
        session_db.add(new_income)
        await session_db.commit()






