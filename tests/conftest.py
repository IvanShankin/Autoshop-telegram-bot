import asyncio
import os
import sys
from contextlib import suppress

import aio_pika
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from src.services.database.database import SQL_DB_URL
from src.services.database import database
from src.redis_dependencies.filling_redis import filling_all_redis

from tests.helpers.helper_fixture import *
from tests.helpers.monkeypatch_data import replacement_redis, replacement_fake_bot, replacement_fake_keyboard, replacement_exception_aiogram

load_dotenv()  # Загружает переменные из .env
MODE = os.getenv('MODE')
RABBITMQ_URL = os.getenv('RABBITMQ_URL')

import pytest_asyncio
from src.services.database.filling_database import create_database

consumer_started = False

# ---------- фикстуры ----------

@pytest_asyncio.fixture(scope='session', autouse=True)
async def create_database_fixture():
    if MODE != "TEST":
        raise Exception("Используется основная БД!")

    # Создаем БД
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

@pytest_asyncio.fixture(scope="function")
async def replacement_needed_modules(
        replacement_redis,
        replacement_fake_bot,
        replacement_fake_keyboard,
        replacement_exception_aiogram,
):
    """Заменит все необходимые модули"""
    yield

@pytest_asyncio.fixture(scope="function")
async def start_consumer():
    """ Запускает consumer и корректно его останавливает по завершению теста. """
    from src.broker.consumer import consume_events

    started_event = asyncio.Event()
    stop_event = asyncio.Event()

    task = asyncio.create_task(consume_events(started_event, stop_event))

    # ждём сигнала, что consumer реально подписался на очередь
    await asyncio.wait_for(started_event.wait(), timeout=7.0)

    try:
        yield
    finally:
        # даём время аккуратно завершить обработку текущего сообщения
        stop_event.set()
        try:
            # ждем, но не вечно — чтобы тест не зависал
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            # если не завершился — принудительно отменяем
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

@pytest_asyncio.fixture(scope="function")
async def clean_rabbit(start_consumer):
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    queues_to_purge = ["events_db"]
    for queue_name in queues_to_purge:
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.purge()
    await channel.close()
    await connection.close()
    yield

@pytest_asyncio.fixture
async def get_engine():
    engine = create_async_engine(SQL_DB_URL)
    yield engine
    await engine.dispose()