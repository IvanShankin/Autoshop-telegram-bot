from redis.asyncio import Redis

from src.config import get_config

redis_client: Redis | None = None


async def init_redis():
    global redis_client

    conf = get_config()

    redis_client = Redis(
        host=conf.env.redis_host,
        port=conf.env.redis_port,
        db=0,
        decode_responses=True,
    )


async def close_redis():
    global redis_client

    if redis_client:
        await redis_client.aclose()


def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis not initialized")

    return redis_client