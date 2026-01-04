from contextlib import asynccontextmanager
from redis.asyncio import Redis  # Асинхронный клиент

from src.config import get_config


@asynccontextmanager
async def get_redis():
    conf = get_config()
    redis = Redis(
        host=conf.env.redis_host,
        port=conf.env.redis_port,
        db=0,
        decode_responses=True
    )
    try:
        yield redis
    finally:
        await redis.aclose()