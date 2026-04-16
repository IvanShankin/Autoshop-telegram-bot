from src.config import Config
from src.repository.redis import SubscriptionCacheRepository


class SubscriptionService:

    def __init__(
        self,
        subscription_cache_repo: SubscriptionCacheRepository,
        conf: Config,
    ):
        self.subscription_cache_repo = subscription_cache_repo
        self.conf = conf

    async def set(self, user_id: int) -> None:
        return await self.subscription_cache_repo.set(user_id, int(self.conf.redis_time_storage.subscription_prompt.total_seconds()))

    async def get(self, user_id: int) -> str | None:
        return await self.subscription_cache_repo.get(user_id)

    async def delete(self, user_id: int) -> None:
        return await self.subscription_cache_repo.delete(user_id)
