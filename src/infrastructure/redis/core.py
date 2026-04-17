from redis.asyncio import Redis

from src.config import Config


def init_redis(conf: Config) -> Redis:
    global redis_client

    redis_client = Redis(
        host=conf.env.redis_host,
        port=conf.env.redis_port,
        db=0,
        decode_responses=True,
    )
    return redis_client


async def close_redis(redis: Redis):
    await redis.aclose()

