import orjson
from sqlalchemy import select

from src.database.core_models import Users
from src.database.database import get_db
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.time_storage import TIME_USER


async def get_user(user_id: int)->Users | None:
    """Берёт с redis, если там нет, то возьмёт с БД и запишет в redis. """
    async with get_redis() as session_redis:
        user_redis = session_redis.get(f'user:{user_id}')
        if user_redis:
            return Users(**orjson.loads(user_redis))

    async with get_db() as session_db:
        result_db = await session_db.execute(select(Users).where(Users.user_id == user_id))
        user_db = result_db.scalar_one_or_none()
        if user_db:
            async with get_redis() as session_redis:
                session_redis.setex(f'user:{user_id}', TIME_USER, orjson.dumps(user_db.to_dict()))
            return user_db
        else:
            return None


