import asyncio
import os
import sys
from contextlib import asynccontextmanager

import fakeredis.aioredis
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from src.database.events import core_event
from src.redis_dependencies.core_redis import get_redis
from src.redis_dependencies.filling_redis import filling_all_redis

load_dotenv()  # Загружает переменные из .env
MODE = os.getenv('MODE')

import pytest_asyncio
from src.database.filling_database import create_database

# для monkeypatch
from src.database import database
from src.redis_dependencies import core_redis

# ---------- фикстуры ----------

@pytest_asyncio.fixture(scope='session', autouse=True)
async def create_database_fixture():
    if MODE != "TEST":
        raise Exception("Используется основная БД!")

    # Создаем таблицы
    await create_database()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_db(monkeypatch):
    # создаём новый engine для теста
    test_engine = create_async_engine(database.SQL_DB_URL, future=True)

    # подменяем глобальный engine и sessionmaker внутри database.py
    monkeypatch.setattr(database, "engine", test_engine)
    database.session_local.configure(bind=test_engine)

    # дропаем и создаём таблицы
    async with test_engine.begin() as conn:
        await conn.run_sync(database.Base.metadata.drop_all)
        await conn.run_sync(database.Base.metadata.create_all)

    yield

    await test_engine.dispose()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_redis(replacement_redis):
    async with get_redis() as session_redis:
        await session_redis.flushdb()

    await filling_all_redis()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_redis(monkeypatch):
    @asynccontextmanager
    async def get_fakeredis():
        redis = await fakeredis.aioredis.FakeRedis().client()
        try:
            yield redis
        finally:
            await redis.close()

    monkeypatch.setattr(core_redis, "get_redis", get_fakeredis) # замена функции get_redis на собственную

@pytest_asyncio.fixture(scope="function", autouse=True)
async def reset_event_queue():
    """Пересоздаём event_queue перед каждым тестом, чтобы в нём не оставались старые события"""
    new_q = asyncio.Queue()
    core_event.event_queue = new_q

    # пробегаем по всем загруженным модулям и заменяем, если где-то был импорт event_queue
    for mod in list(sys.modules.values()):
        if not mod:
            continue
        if hasattr(mod, "event_queue"):
            setattr(mod, "event_queue", new_q)

    yield