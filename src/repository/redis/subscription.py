from src.repository.redis.base import BaseRedisRepo


class SubscriptionCacheRepository(BaseRedisRepo):

    async def set(self, user_id: str) -> None:
        return await self.redis_session.setex(
            f"subscription_prompt:{user_id}",
            self.conf.redis_time_storage.subscription_prompt,
            "_"
        )

    async def get(self, user_id: str) -> str | None:
        return await self.redis_session.get(
            f"subscription_prompt:{user_id}",
        )

    async def delete(self, user_id: str) -> None:
        return await self.redis_session.delete(
            f"subscription_prompt:{user_id}",
        )