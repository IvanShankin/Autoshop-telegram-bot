import sys
import types
from contextlib import asynccontextmanager

import fakeredis
import pytest_asyncio

from src.redis_dependencies import core_redis


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.sent.append((chat_id, text, kwargs))

    def get_message(self, chat_id: int, text: str) -> bool:
        """Проверяет наличие сообщения с данными параметрами"""
        return any(c == chat_id and t == text for c, t, _ in self.sent)


@pytest_asyncio.fixture(scope="function", autouse=True)
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
    await redis.close()

@pytest_asyncio.fixture(scope="function")
async def replacement_fake_bot(monkeypatch) -> FakeBot:
    fake_bot = FakeBot()

    sys.modules.pop("src.bot_instance", None) # удаление модуля
    fake_module = types.ModuleType("src.bot_instance") # создаём поддельный модуль
    fake_module.bot = fake_bot
    fake_module.create_bot = lambda: (fake_bot, None)  # если где-то вызывают create_bot

    # подменяем во всех местах, где импортируется src.bot_instance
    monkeypatch.setitem(sys.modules, "src.bot_instance", fake_module)

    return fake_bot

@pytest_asyncio.fixture(scope="function")
async def replacement_fake_keyboard(monkeypatch):
    def support_kb():
        return True

    fake_module = types.ModuleType("src.modules.core_keyboard")# создаём поддельный модуль
    fake_module.support_kb = support_kb
    monkeypatch.setitem(sys.modules, "src.modules.core_keyboard", fake_module)# подменяем во всех местах, где импортируется


