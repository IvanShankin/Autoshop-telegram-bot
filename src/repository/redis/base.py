from typing import TypeVar, Optional, Type, List

from orjson import orjson
from redis.asyncio import Redis

from src.config import Config


T = TypeVar("T")


class BaseRedisRepo:

    def __init__(self, redis_session: Redis, config: Config):
        self.redis_session = redis_session
        self.conf = config

    async def _set_one(self, key: str, value: T, ttl: Optional[int] = None):
        """Устанавливает единичную модель `model`"""
        data = orjson.dumps(value.model_dump())

        if ttl:
            await self.redis_session.setex(key, ttl, data)
        else:
            await self.redis_session.set(key, data)

    async def _get_one(self, key: str, model: Type[T]) -> Optional[T]:
        """Извлекает единичную модель `model`"""
        raw = await self.redis_session.get(key)
        if not raw:
            return None

        return model.model_validate(orjson.loads(raw))

    async def _set_many(self, key: str, values: List[T], ttl: Optional[int] = None):
        """Устанавливает список из `model`"""
        data = orjson.dumps([v.model_dump() for v in values])

        if ttl:
            await self.redis_session.setex(key, ttl, data)
        else:
            await self.redis_session.set(key, data)

    async def _get_many(self, key: str, model: Type[T]) -> List[T]:
        """Извлекает список `model`"""
        raw = await self.redis_session.get(key)
        if not raw:
            return []

        return [model.model_validate(item) for item in orjson.loads(raw)]

    async def delete_keys_by_pattern(self, pattern: str) -> int:
        """
        Удаляет все ключи, соответствующие шаблону. Пример: 'user:*'
        :return int: количество удалённых записей
        """
        count = 0
        async for key in self.redis_session.scan_iter(match=pattern):
            await self.redis_session.delete(key)
            count += 1
        return count

    async def bulk_set(self, items: list[tuple[str, bytes, int]]):
        """
        :param items: List[tuple[ключ, данные, ttl]]
        """
        async with self.redis_session.pipeline(transaction=False) as pipe:
            for key, value, ttl in items:
                if ttl and ttl > 1:
                    await pipe.setex(key, ttl, value)
                else:
                    await pipe.set(key, value)
            await pipe.execute()