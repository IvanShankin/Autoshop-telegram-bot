import importlib
import os
import shutil
import sys
import types
from typing import Generator

import fakeredis
import pytest
import pytest_asyncio

from tests.helpers.func_fabrics.fake_objects_fabric import crypto_provider_factory
from src._bot_actions.throttler import RateLimiter
from src.application._secrets.crypto_context import set_crypto_context
from src.config import get_config, set_config, Config, FilePathAndKey, FileKeysConf
from src.infrastructure.redis import core
from tests.helpers.fake_aiogram.fake_aiogram_module import FakeBot

fake_bot = FakeBot()


class FakePublishEventHandler:
    def __init__(self):
        self.counter_send_log = 0
        self.counter_ban_account = 0
        self.counter_delete_ban_account = 0
        self.counter_admin_update_balance = 0
        self.counter_error_message_effect = 0
        self.counter_create_ui_image = 0
        self.counter_voucher_activated = 0

    async def send_log(self, *args, **kwargs):
        self.counter_send_log += 1

    async def ban_account(self, *args, **kwargs):
        self.counter_ban_account += 1

    async def delete_ban_account(self, *args, **kwargs):
        self.counter_delete_ban_account += 1

    async def admin_update_balance(self, *args, **kwargs):
        self.counter_admin_update_balance += 1

    async def error_message_effect(self, *args, **kwargs):
        self.counter_error_message_effect += 1

    async def create_ui_image(self, *args, **kwargs):
        self.counter_create_ui_image += 1

    async def voucher_activated(self, *args, **kwargs):
        self.counter_voucher_activated += 1


async def replacement_redis(monkeypatch):
    redis = fakeredis.aioredis.FakeRedis()

    def get_fakeredis():
        return redis

    # заменяем в core
    monkeypatch.setattr(core, "get_redis", get_fakeredis)

    # заменяем во всех уже загруженных модулях, где есть get_redis
    for name, module in sys.modules.items():
        if hasattr(module, "get_redis"):
            monkeypatch.setattr(module, "get_redis", get_fakeredis, raising=False)

    yield redis
    await redis.aclose()


def replacement_fake_bot(monkeypatch):
    pass
    # from src.config import get_config
    # # очищаем бота
    # fake_bot.clear()
    #
    # # удаляем старый модуль полностью
    # sys.modules.pop("src._bot_actions.bot_instance", None)
    #
    # # Создаём поддельный модуль
    # fake_module = types.ModuleType("src._bot_actions.bot_instance")
    #
    # async def fake_get_bot():
    #     return fake_bot
    #
    # async def get_dispatcher():
    #     return None
    #
    # async def run_bot():
    #     return fake_bot, None
    #
    # fake_module.GLOBAL_RATE_LIMITER = RateLimiter(max_calls=get_config().different.rate_send_msg_limit, period=1.0)
    #
    # fake_module.get_bot = fake_get_bot
    # fake_module.get_dispatcher = get_dispatcher
    # fake_module.run_bot = run_bot
    # fake_module._bot = fake_bot
    # fake_module._dp = None
    #
    # fake_module.get_bot_logger = fake_get_bot
    # fake_module.get_dispatcher_logger = get_dispatcher
    # fake_module.run_bot_logger = run_bot
    # fake_module._bot_logger = fake_bot
    # fake_module._dp_logger = None
    #
    # # Подменяем модуль в sys.modules
    # monkeypatch.setitem(sys.modules, "src._bot_actions.bot_instance", fake_module)
    #
    # import src._bot_actions.messages
    # importlib.reload(src._bot_actions.messages)
    # importlib.reload(src._bot_actions.messages.edit)
    # importlib.reload(src._bot_actions.messages.send)
    #
    # # Очищаем сообщения перед каждым тестом
    # fake_bot.sent.clear()
    #
    # return fake_bot



@pytest_asyncio.fixture(scope="function", autouse=True)
async def create_crypto_context_fix():
    """Создаёт CryptoContext"""
    try:
        crypto_provider = crypto_provider_factory()
        set_crypto_context(crypto_provider.get())
    except RuntimeError:
        pass


@pytest_asyncio.fixture(scope="function", autouse=True)
async def set_need_config():
    conf = get_config()

    # conf.app.type_account_services = ["telegram"]

    set_config(conf)



@pytest.fixture(autouse=True)
def publish_event_service_fix(container_fix):
    container_fix.publish_event_handler = FakePublishEventHandler()
