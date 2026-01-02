import asyncio
import os
import sys
import aio_pika

from contextlib import suppress


from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from tests.helpers.monkeypatch_data import (
    replacement_redis,
    replacement_fake_bot,
    replacement_pyth_account,
    replacement_pyth_ui_image,
    replacement_pyth_sent_mass_msg_image,
    create_crypto_context_fix,
)


from src.services.database.core.database import SQL_DB_URL
from src.services.database import core
from src.services.redis.core_redis import get_redis

from tests.helpers.helper_fixture import *

from tests.helpers.fake_aiogram.fake_aiogram import patch_fake_aiogram

# ИМПОРТЫ НЕ УБИРАТЬ, ОНИ ИСПОЛЬЗУЮТСЯ В ТЕСТАХ ПОДГРУЖАЯСЬ С conftest.py

load_dotenv()  # Загружает переменные из .env
MODE = os.getenv('MODE')
RABBITMQ_URL = os.getenv('RABBITMQ_URL')

import pytest_asyncio
from src.services.database.core.filling_database import create_table

consumer_started = False

if "aiogram" in sys.modules:
    raise RuntimeError("aiogram был импортирован слишком рано! Используй локальный импорт в функции/фикстуре.")



# ---------- фикстуры ----------

@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_needed_modules(
        replacement_redis_fix,
        replacement_fake_bot_fix,
        patch_fake_aiogram,
        replacement_pyth_ui_image_fix,
        replacement_pyth_sent_mass_msg_image_fix,
):
    """Заменит все необходимые модули"""
    yield



@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_redis_fix(monkeypatch):
    async for _ in replacement_redis(monkeypatch):
        yield


@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_fake_bot_fix(monkeypatch, replacement_pyth_ui_image_fix):
    return replacement_fake_bot(monkeypatch)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_pyth_account_fix(monkeypatch, replacement_pyth_ui_image_fix):
    for _ in replacement_pyth_account(monkeypatch):
        yield


@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_pyth_ui_image_fix(monkeypatch, tmp_path):
    for _ in replacement_pyth_ui_image(monkeypatch, tmp_path):
        yield


@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_pyth_sent_mass_msg_image_fix(monkeypatch, tmp_path):
    for _ in replacement_pyth_sent_mass_msg_image(monkeypatch, tmp_path):
        yield



@pytest_asyncio.fixture(scope='function', autouse=True)
async def create_database_fixture(replacement_needed_modules):
    if MODE != "TEST":
        raise Exception("Используется основная БД!")

    # Создаем БД
    await create_table()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_db(monkeypatch):
    # создаём новый engine для теста
    test_engine = create_async_engine(core.SQL_DB_URL, future=True)

    # подменяем глобальный engine и sessionmaker внутри core.py
    monkeypatch.setattr(core, "engine", test_engine)
    core.session_local.configure(bind=test_engine)

    # дропаем и создаём таблицы
    async with test_engine.begin() as conn:
        await conn.run_sync(core.Base.metadata.drop_all)
        await conn.run_sync(core.Base.metadata.create_all)

    yield

    await test_engine.dispose()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_redis(replacement_redis_fix):
    from src.services.redis.filling_redis import filling_all_redis
    async with get_redis() as session_redis:
        await session_redis.flushdb()

    await filling_all_redis()


@pytest_asyncio.fixture(scope="function")
async def start_consumer():
    """ Запускает consumer и корректно его останавливает по завершению теста. """
    from src.broker.consumer import _run_single_consumer_loop

    started_event = asyncio.Event()
    stop_event = asyncio.Event()

    task = asyncio.create_task(_run_single_consumer_loop(started_event, stop_event))

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