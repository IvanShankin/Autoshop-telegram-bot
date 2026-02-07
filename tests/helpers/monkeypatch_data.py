import importlib
import os
import shutil
import sys
import types
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import fakeredis
import pytest
import pytest_asyncio

from src.bot_actions.throttler import RateLimiter
from src.config import get_config, set_config, Config, FilePathAndKey, FileKeysConf
from src.services.secrets import init_crypto_context
from tests.helpers.fake_aiogram.fake_aiogram_module import FakeBot
from src.services.redis import core_redis

fake_bot = FakeBot()


async def replacement_redis(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis()

    @asynccontextmanager
    async def get_fakeredis():
        yield redis

    # заменяем в core_redis
    monkeypatch.setattr(core_redis, "get_redis", get_fakeredis)

    # заменяем во всех уже загруженных модулях, где есть get_redis
    for name, module in sys.modules.items():
        if hasattr(module, "get_redis"):
            monkeypatch.setattr(module, "get_redis", get_fakeredis, raising=False)

    yield redis
    await redis.aclose()


def replacement_fake_bot(monkeypatch):
    from src.config import get_config
    # очищаем бота
    fake_bot.clear()

    # удаляем старый модуль полностью
    sys.modules.pop("src.bot_actions.bot_instance", None)

    # Создаём поддельный модуль
    fake_module = types.ModuleType("src.bot_actions.bot_instance")

    async def fake_get_bot():
        return fake_bot

    async def get_dispatcher():
        return None

    async def run_bot():
        return fake_bot, None

    fake_module.GLOBAL_RATE_LIMITER = RateLimiter(max_calls=get_config().different.rate_send_msg_limit, period=1.0)

    fake_module.get_bot = fake_get_bot
    fake_module.get_dispatcher = get_dispatcher
    fake_module.run_bot = run_bot
    fake_module._bot = fake_bot
    fake_module._dp = None

    fake_module.get_bot_logger = fake_get_bot
    fake_module.get_dispatcher_logger = get_dispatcher
    fake_module.run_bot_logger = run_bot
    fake_module._bot_logger = fake_bot
    fake_module._dp_logger = None

    # Подменяем модуль в sys.modules
    monkeypatch.setitem(sys.modules, "src.bot_actions.bot_instance", fake_module)

    import src.bot_actions.messages
    importlib.reload(src.bot_actions.messages)
    importlib.reload(src.bot_actions.messages.edit)
    importlib.reload(src.bot_actions.messages.send)

    # Очищаем сообщения перед каждым тестом
    fake_bot.sent.clear()

    return fake_bot


def replacement_path_product(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.products_dir.parent
    product_dir = base_dir / "product_test"

    conf.paths.products_dir = product_dir
    conf.paths.accounts_dir = product_dir / "accounts_test"
    conf.paths.universals_dir = product_dir / "universals_test"


    set_config(conf)

    os.makedirs(product_dir, exist_ok=True)
    os.makedirs(conf.paths.accounts_dir, exist_ok=True)
    os.makedirs(conf.paths.universals_dir, exist_ok=True)

    yield

    if os.path.isdir(product_dir):
        shutil.rmtree(product_dir) # удаляет директорию созданную для тестов

    yield


def replacement_path_ui_image(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.ui_sections_dir.parent
    new_ui_section_dir = base_dir / "ui_sections_test"
    conf.paths.ui_sections_dir = new_ui_section_dir

    os.makedirs(new_ui_section_dir, exist_ok=True)

    set_config(conf)

    yield

    if os.path.isdir(new_ui_section_dir):
        shutil.rmtree(new_ui_section_dir)  # удаляет директорию созданную для тестов

    yield


def replacement_path_sent_mass_msg_image(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.sent_mass_msg_image_dir.parent
    new_sent_mass_msg_dir = base_dir / "sent_mass_msg_image_test"
    conf.paths.sent_mass_msg_image_dir = new_sent_mass_msg_dir

    os.makedirs(new_sent_mass_msg_dir, exist_ok=True)

    set_config(conf)

    yield

    if os.path.isdir(new_sent_mass_msg_dir):
        shutil.rmtree(new_sent_mass_msg_dir)  # удаляет директорию созданную для тестов

    yield


def replacement_path_temp(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.temp_dir.parent
    new_temp_dir = base_dir / "temp_test"
    conf.paths.temp_dir = new_temp_dir

    os.makedirs(new_temp_dir, exist_ok=True)

    set_config(conf)

    yield

    if os.path.isdir(new_temp_dir):
        shutil.rmtree(new_temp_dir)  # удаляет директорию созданную для тестов

    yield


def replacement_path_files(conf: Config) -> Generator[None, None, None]:
    base_dir = conf.paths.files_dir.parent
    new_files_dir = base_dir / "files_test"
    conf.paths.files_dir = new_files_dir

    os.makedirs(new_files_dir, exist_ok=True)

    conf.file_keys = FileKeysConf(
        example_zip_for_universal_import_key=FilePathAndKey(
            key="example_zip_for_universal_import",
            path=new_files_dir / "example_zip_for_universal_import.zip",
            name_in_dir_with_files="example_zip_for_universal_import.zip"
        ),
        example_zip_for_import_tg_acc_key=FilePathAndKey(
            key="example_zip_for_import_tg_acc",
            path=new_files_dir / "example_zip_for_import_tg_acc.zip",
            name_in_dir_with_files="example_zip_for_import_tg_acc.zip"
        ),
        example_csv_for_import_other_acc_key=FilePathAndKey(
            key="example_csv_for_import_other_acc",
            path=new_files_dir / "example_csv_for_import_other_acc.csv",
            name_in_dir_with_files="example_csv_for_import_other_acc.csv"
        )
    )

    set_config(conf)

    yield

    if os.path.isdir(new_files_dir):
        shutil.rmtree(new_files_dir)  # удаляет директорию созданную для тестов

    yield


def replace_paths() -> Generator[None, None, None]:
    conf = get_config()

    path_products = replacement_path_product(conf)
    path_ui_image = replacement_path_ui_image(conf)
    path_sent_mass_msg_image = replacement_path_sent_mass_msg_image(conf)
    path_temp = replacement_path_temp(conf)
    path_files = replacement_path_files(conf)

    # создаст временные директории, второй раз удалит их
    next(path_products)
    next(path_ui_image)
    next(path_sent_mass_msg_image)
    next(path_temp)
    next(path_files)

    yield

    # удалит временные директории
    next(path_products)
    next(path_ui_image)
    next(path_sent_mass_msg_image)
    next(path_temp)
    next(path_files)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def create_crypto_context_fix():
    """Создаёт CryptoContext"""
    try:
        init_crypto_context()
    except RuntimeError:
        pass


@pytest_asyncio.fixture(scope="function", autouse=True)
async def set_need_config():
    conf = get_config()

    conf.app.type_account_services = ["telegram"]

    set_config(conf)


@pytest.fixture
def fake_storage(monkeypatch):
    storage = MagicMock()

    from src.services.database.backups import backup_db as core_modul
    monkeypatch.setattr(
        core_modul,
        "get_storage_client",
        lambda: storage
    )

    return storage
