import pytest

from src.services.redis.core_redis import get_redis
from src.services.redis.tasks import _set_dollar_rate


@pytest.mark.asyncio
async def test_set_dollar_rate():
    await _set_dollar_rate()
    async with get_redis() as session_redis:
        data_redis = await session_redis.get('dollar_rate')
        rate = float(data_redis)
        assert rate