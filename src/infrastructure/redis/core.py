from redis.asyncio import Redis

from src.config import get_config

redis_client: Redis | None = None


def init_redis() -> Redis:
    global redis_client

    conf = get_config()

    redis_client = Redis(
        host=conf.env.redis_host,
        port=conf.env.redis_port,
        db=0,
        decode_responses=True,
    )
    return redis_client


async def close_redis():
    global redis_client

    if redis_client:
        await redis_client.aclose()

