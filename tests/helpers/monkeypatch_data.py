import base64
import importlib
import os
import shutil
import sys
import types
from contextlib import asynccontextmanager

import fakeredis
import pytest_asyncio
from dotenv import load_dotenv

from src.bot_actions.throttler import RateLimiter
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
    from src.config import RATE_SEND_MSG_LIMIT
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

    fake_module.GLOBAL_RATE_LIMITER = RateLimiter(max_calls=RATE_SEND_MSG_LIMIT, period=1.0)

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


def replacement_pyth_account(monkeypatch):
    from src import config
    from src.services.database.selling_accounts.actions import action_purchase
    from src.services.filesystem import account_actions

    new_account_dir = config.MEDIA_DIR / "accounts_test"

    monkeypatch.setattr(config, 'ACCOUNTS_DIR', new_account_dir)
    monkeypatch.setattr(action_purchase, 'ACCOUNTS_DIR', new_account_dir)
    monkeypatch.setattr(account_actions, 'ACCOUNTS_DIR', new_account_dir)

    yield

    if os.path.isdir(new_account_dir):
        shutil.rmtree(new_account_dir) # удаляет директорию созданную для тестов


def replacement_pyth_ui_image(monkeypatch, tmp_path):
    from src.services.database.system.actions import actions as actions_modul
    from src.utils import ui_images_data

    new_ui_section_dir = tmp_path / "ui_sections_test"
    monkeypatch.setattr(actions_modul, "UI_SECTIONS", new_ui_section_dir)
    monkeypatch.setattr(ui_images_data, "UI_SECTIONS", new_ui_section_dir)

    yield

    if os.path.isdir(new_ui_section_dir):
        shutil.rmtree(new_ui_section_dir)  # удаляет директорию созданную для тестов


def replacement_pyth_sent_mass_msg_image(monkeypatch, tmp_path):
    from src.bot_actions.messages import mass_tg_mailing as messages_modul

    new_sent_mass_msg_dir = tmp_path / "sent_mass_msg_image_test"
    monkeypatch.setattr(messages_modul, "SENT_MASS_MSG_IMAGE_DIR", new_sent_mass_msg_dir)

    yield

    if os.path.isdir(new_sent_mass_msg_dir):
        shutil.rmtree(new_sent_mass_msg_dir)  # удаляет директорию созданную для тестов


def create_crypto_context():
    """Создаёт CryptoContext"""
    from src.services.secrets.crypto import CryptoContext, set_crypto_context
    try:
        kek_base64 = b"TjIXMqYwYPfFFnJLGAHD0IJLRo4OugMtm0YovbGpPaU="
        dek_base64 = b"BtMAKbeZowwFcj87524XOoa9Ympm0QFPnRwAhXqjJUk="
        nonce = os.urandom(12)

        crypto = CryptoContext(
            kek = base64.b64decode(kek_base64),
            dek = base64.b64decode(dek_base64),
            nonce_b64_dek = base64.b64encode(nonce).decode('utf-8')
        )
        set_crypto_context(crypto)
    except RuntimeError: # если уже имеется
        pass


@pytest_asyncio.fixture(scope="function", autouse=True)
async def create_crypto_context_fix():
    """Создаёт CryptoContext"""
    create_crypto_context()


def replace_get_secret(monkeypatch):
    #  Подменяем get_secret ДО вызова функции
    import src.services.secrets.loader as loader

    monkeypatch.setattr(
        loader,
        "get_secret",
        lambda name: os.getenv(name),
    )

    import src.services.secrets.secret_conf as config
    config._settings = None



