import os

from contextlib import asynccontextmanager
from redis.asyncio import Redis  # Асинхронный клиент
from dotenv import load_dotenv

load_dotenv()
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))

@asynccontextmanager
async def get_redis():
    redis = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=0,
        decode_responses=True
    )
    try:
        yield redis
    finally:
        await redis.aclose()