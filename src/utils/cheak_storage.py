from typing import Type, Callable, Optional, Any, Tuple

import orjson
from sqlalchemy import select

from src.database.database import get_db
from src.redis_dependencies.core_redis import get_redis


async def view_redis_and_db(
    redis_key: str,
    db_model: Type,
    condition_where: Optional[Any],
    get_fun: Callable[[Any], Any],
    ttl: int = 300
) -> Tuple[Optional[Any], str]:
    """
    Достаёт данные из Redis, если нет — из БД и кладёт в Redis.

    :param redis_key: ключ в Redis
    :param db_model: модель SQLAlchemy
    :param condition_where: условие для фильтрации (select.where(...))
    :param get_fun: функция обработки результата SQLAlchemy execute()
    :param ttl: TTL для кэширования (по умолчанию 300 сек)
    :return: кортеж (данные, источник: 'redis' | 'db')
    """
    # пробуем из Redis
    async with get_redis() as session_redis:
        cached = await session_redis.get(redis_key)
        if cached:
            return orjson.loads(cached), "redis"

    # если нет в Redis — берём из БД
    async with get_db() as session_db:
        if condition_where is not None:
            result_db = await session_db.execute(select(db_model).where(condition_where))
        else:
            result_db = await session_db.execute(select(db_model))

        db_data = get_fun(result_db)

        if db_data is not None:
            async with get_redis() as session_redis:
                await session_redis.setex(redis_key, ttl, orjson.dumps(db_data))

        return db_data, "db"