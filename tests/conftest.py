import logging

import aiohttp

from tests.helpers.func_fabrics.fake_objects_fabric import secret_storage_factory, crypto_provider_factory
from src.database.creating import create_database, create_table
from tests.helpers.import_tracker import enable_import_tracking

# В ТЕСТАХ НЕЛЬЗЯ ИСПОЛЬЗОВАТЬ AIOGRAM, ИНАЧЕ БУДЕТ БЕСКОНЕЧНАЯ ЗАГРУЗКА В РЕЖИМЕ ОТЛАДКИ
enable_import_tracking("aiogram")

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine


from src.application.crypto.secrets_storage import GetSecret
from src.config import set_config, RuntimeConfig, get_config, init_config
from src.database import Base
from src.infrastructure.logger.core_logger import setup_logging
from tests.helpers.fixtures.replace_paths import replace_paths_in_config
from tests.helpers.monkeypatch_data import (
    replacement_fake_bot,
)

from tests.helpers.fake_aiogram.fake_aiogram import patch_fake_aiogram

from tests.helpers.fixtures.helper_fixture import (
    container_fix, )
# ИМПОРТЫ НЕ УБИРАТЬ, ОНИ ИСПОЛЬЗУЮТСЯ В ТЕСТАХ ПОДГРУЖАЯСЬ

load_dotenv()  # Загружает переменные из .env
MODE = os.getenv('MODE')
RABBITMQ_URL = os.getenv('RABBITMQ_URL')
import pytest_asyncio


if MODE != "TEST":
    raise Exception("Используется основная БД!")


# ---------- фикстуры ----------


@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_needed_modules(
    replacement_fake_bot_fix,
    patch_fake_aiogram,
    replace_paths_in_config,
    replacement_logger_fix,
):
    """Заменит все необходимые модули"""
    yield



@pytest_asyncio.fixture(scope="function", autouse=True)
async def replacement_fake_bot_fix(monkeypatch, replace_paths_in_config):
    return replacement_fake_bot(monkeypatch)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_conf_fix(get_secret_fix):
    """ВРЕМЕННАЯ ФИКСТУРА ПОКА ПОЛНОСТЬЮ НЕ УБЕРУ ПОЛУЧЕНИЕ КОНФИГА"""
    http_session = aiohttp.ClientSession()
    config = init_config(get_secret_fix.execute)


@pytest_asyncio.fixture(scope="session")
async def replacement_logger_fix():
    path_log_file = get_config().paths.log_file
    test_log_file = path_log_file.parent / "auto_shop_bot_tests.log"
    setup_logging(test_log_file)
    yield


@pytest_asyncio.fixture(scope='function', autouse=True)
async def create_database_fixture(replacement_needed_modules, container_fix):
    if MODE != "TEST":
        raise Exception("Используется основная БД!")

    # Создаем БД
    await create_database(container_fix.config)
    await create_table(container_fix.config)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_db(monkeypatch, create_database_fixture):
    conf = get_config()
    old_engine = conf.db_connection.engine
    if old_engine is not None:
        await old_engine.dispose()
    # создаём новый engine для теста
    test_engine = create_async_engine(
        conf.db_connection.sql_db_url,
        future=True,
        connect_args={"statement_cache_size": 0},
    )

    conf.db_connection.engine = test_engine
    conf.db_connection.session_local.configure(bind=test_engine)

    set_config(conf)

    # дропаем и создаём таблицы
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_redis(container_fix):
    await container_fix.session_redis.flushdb()


@pytest_asyncio.fixture
async def get_engine():
    engine = create_async_engine(
        get_config().db_connection.sql_db_url,
        connect_args={"statement_cache_size": 0},
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def get_secret_fix():
    get_secret = GetSecret(
        storage=secret_storage_factory(),
        crypto_provider=crypto_provider_factory(),
        logger=logging.getLogger(__name__),
        runtime_conf=RuntimeConfig()
    )

    yield get_secret
