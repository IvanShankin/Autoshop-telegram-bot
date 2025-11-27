from datetime import datetime, UTC

from dateutil.parser import parse
from orjson import orjson
from sqlalchemy import select, update

from src.services.redis.core_redis import get_redis
from src.services.redis.time_storage import TIME_USER
from src.services.database.core.database import get_db
from src.services.database.users.models import Users


async def get_user(user_id: int, username: str = None, update_last_used: bool = False)->Users | None:
    """
    Берёт с redis, если там нет, то возьмёт с БД и запишет в redis.
    :param username: обновит username если он не сходится с имеющимся
    """
    async with get_redis() as session_redis:
        user_redis = await session_redis.get(f'user:{user_id}')
        if user_redis:
            data = orjson.loads(user_redis)
            user = Users(**data)
            user.created_at = parse(data["created_at"])
            user.last_used = parse(data["last_used"])
            if username and user.username and user.username != username: # если username расходится
                user.username = username
                user = await update_user(user_id=user.user_id, **(user.to_dict()))
            return user

    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users).where(Users.user_id == user_id))
        user_db = result_db.scalar_one_or_none()
        if user_db:
            update_data = {}
            if username and user_db.username and user_db.username != username: # если username расходится
                update_data['username'] = username
            if update_last_used: update_data['last_used'] = datetime.now(UTC)

            if update_data:
                await update_user(user_id=user_id, **update_data)
            else:
                # redis обновляем только тут ибо если попали в условие для вызова функции update_user,
                # то в этой функции обновится redis
                async with get_redis() as session_redis:
                    await session_redis.setex(f'user:{user_id}', TIME_USER, orjson.dumps(user_db.to_dict()))

            return user_db
        else:
            return None


async def get_user_by_ref_code(code: str) -> Users | None:
    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users).where(Users.unique_referral_code == code))
        return result_db.scalars().first()


async def update_user(
    user_id: int,
    username: str = None,
    language: str = None,
    unique_referral_code: str = None,
    balance: int = None,
    total_sum_replenishment: int = None,
    total_profit_from_referrals: int = None,
    last_used: datetime = None,
) -> Users:
    """
    Обновляет данные пользователя в БД и Redis.
    """
    update_data = {}
    if username is not None: update_data['username'] = username
    if language is not None: update_data['language'] = language
    if unique_referral_code is not None: update_data['unique_referral_code'] = unique_referral_code
    if balance is not None: update_data['balance'] = balance
    if total_sum_replenishment is not None: update_data['total_sum_replenishment'] = total_sum_replenishment
    if total_profit_from_referrals is not None: update_data['total_profit_from_referrals'] = total_profit_from_referrals
    if last_used is not None: update_data['last_used'] = last_used

    # Обновляем в БД
    async with get_db() as session_db:
        # Выполняем обновление
        result = await session_db.execute(
            update(Users)
            .where(Users.user_id == user_id)
            .values(**update_data)
            .returning(Users)
        )
        user = result.scalar_one()
        await session_db.commit()

    # Обновляем в Redis
    async with get_redis() as session_redis:
        await session_redis.setex(
            f'user:{user.user_id}',
            TIME_USER,
            orjson.dumps(user.to_dict())
        )
    return user
