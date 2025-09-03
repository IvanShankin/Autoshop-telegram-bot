import orjson
from sqlalchemy import select, update

from dateutil.parser import parse
from src.database.core_models import Users
from src.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.time_storage import TIME_USER


async def get_user(user_id: int)->Users | None:
    """Берёт с redis, если там нет, то возьмёт с БД и запишет в redis. """
    async with get_redis() as session_redis:
        user_redis = await session_redis.get(f'user:{user_id}')
        if user_redis:
            data = orjson.loads(user_redis)
            user = Users(
                user_id=data["user_id"],
                username=data.get("username"),
                language=data.get("language"),
                unique_referral_code=data.get("unique_referral_code"),
                balance=data.get("balance", 0),
                total_sum_replenishment=data.get("total_sum_replenishment", 0),
                total_profit_from_referrals=data.get("total_profit_from_referrals", 0),
                created_at=parse(data["created_at"]) if data.get("created_at") else None,
            )
            return user

    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users).where(Users.user_id == user_id))
        user_db = result_db.scalar_one_or_none()
        if user_db:
            async with get_redis() as session_redis:
                await session_redis.setex(f'user:{user_id}', TIME_USER, orjson.dumps(user_db.to_dict()))
            return user_db
        else:
            return None


async def update_user(user: Users) -> Users:
    """
    Обновляет данные пользователя в БД и Redis.
    :param user Объект пользователя с обновленными данными
    """
    # Обновляем в БД
    async with get_db() as session_db:
        # Выполняем обновление
        result = await session_db.execute(
            update(Users)
            .where(Users.user_id == user.user_id)
            .values(
                username = user.username,
                language = user.language,
                unique_referral_code = user.unique_referral_code,
                balance = user.balance,
                total_sum_replenishment = user.total_sum_replenishment,
                total_profit_from_referrals = user.total_profit_from_referrals
            )
            .returning(Users.created_at)
        )
        created_at = result.scalar_one()
        await session_db.commit()

    user.created_at = created_at # т.к. может поступить дата от пользователя, которая не верна

    # Обновляем в Redis
    async with get_redis() as session_redis:
        await session_redis.setex(
            f'user:{user.user_id}',
            TIME_USER,
            orjson.dumps(user.to_dict())
        )
    return user


