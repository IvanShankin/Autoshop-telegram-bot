from src.repository.redis.base import BaseRedisRepo


class SubscriptionCacheRepository(BaseRedisRepo):

    async def set(self, rate: float) -> None:
        return await self.redis_session.set(
            f"dollar_rate",
            rate
        )

    async def get(self) -> float | None:
        return await self.redis_session.get(
            f"dollar_rate",
        )
