from src.services.redis.core_redis import get_redis


async def get_subscription_prompt(user_id):
    async with get_redis() as session_redis:
        result = await session_redis.get(f'subscription_prompt:{user_id}')
        return bool(result)


async def delete_subscription_prompt(user_id):
    async with get_redis() as session_redis:
        await session_redis.delete(f'subscription_prompt:{user_id}')

