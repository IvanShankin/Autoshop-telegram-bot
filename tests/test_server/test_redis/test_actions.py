import pytest

from src.services.redis.actions import delete_subscription_prompt, get_subscription_prompt
from src.services.redis.core_redis import get_redis


@pytest.mark.asyncio
async def test_delete_subscription_prompt(create_account_category):
    async with get_redis() as session_redis:
        await session_redis.set(f'subscription_prompt:0', '_')

    await delete_subscription_prompt(0)

    async with get_redis() as session_redis:
        assert not await session_redis.get(f'subscription_prompt:0')


@pytest.mark.asyncio
async def test_get_subscription_prompt(create_account_category):
    async with get_redis() as session_redis:
        await session_redis.set(f'subscription_prompt:0', '_')

    assert await get_subscription_prompt(0)