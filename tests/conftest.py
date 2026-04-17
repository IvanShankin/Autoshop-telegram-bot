from tests.helpers.func_fabrics.fake_objects_fabric import secret_storage_factory, crypto_provider_factory
from src.database.creating import create_database, create_table
from tests.helpers.import_tracker import enable_import_tracking

# В ТЕСТАХ НЕЛЬЗЯ ИСПОЛЬЗОВАТЬ AIOGRAM, ИНАЧЕ БУДЕТ БЕСКОНЕЧНАЯ ЗАГРУЗКА В РЕЖИМЕ ОТЛАДКИ
enable_import_tracking("aiogram")

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine


from src.application.crypto.secrets_storage import GetSecret
from src.config import init_config, set_config, RuntimeConfig, get_config
from src.database import Base
from src.utils.core_logger import setup_logging, get_logger
from tests.helpers.fixtures.replace_paths import replace_paths_in_config
from tests.helpers.monkeypatch_data import (
    replacement_fake_bot,
)
from src.infrastructure.redis import init_redis, close_redis

from tests.helpers.fake_aiogram.fake_aiogram import patch_fake_aiogram

from tests.helpers.fixtures.helper_fixture import (
    session_db_fix, fake_tg_client, crypto_bot_provider_fix, secret_storage_fix,
    crypto_provider_fix, container_fix, create_new_user, create_admin_fix,
    create_sent_mass_message, create_referral, create_income_from_referral,
    create_replenishment, create_type_payment, create_settings, create_promo_code,
    create_promo_code_activation, create_voucher, create_translate_category,
    create_category, create_purchase, create_account_storage, create_product_account,
    create_sold_account, create_tg_account_media, create_universal_storage,
    create_product_universal, create_sold_universal, create_ui_image,
    create_transfer_moneys, create_wallet_transaction, create_backup_log,
    create_purchase_request, create_balance_holder,
)
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
async def app_container_for_tests():
    get_secret = GetSecret(
        storage=secret_storage_factory(),
        crypto_provider=crypto_provider_factory(),
        logger=get_logger(__name__),
        runtime_conf=RuntimeConfig()
    )

    init_config(get_secret.execute)
