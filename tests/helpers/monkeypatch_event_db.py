import asyncio
import importlib

import pytest_asyncio

from src.utils.core_logger import get_logger

def monkeypatch_event_db(
        monkeypatch,
        handlers_mod_name: str,
        package_events_mod_name: str,
        event_handler_name: str,
        consumer_mod_name: str = "src.broker.consumer",
):
    """
        Monkeypatch wrapper для promo_code_event_handler:
        - Патчим реализацию (event_handlers модуль)
        - И патчим ссылку в модуле consumer, если consumer уже импортирован.
        - wrapper логирует вызов и выставляет ev.set() в finally.
        """
    ev = asyncio.Event()

    # Импортируем модули (reload на случай, если они уже загружены)
    handlers_mod = importlib.import_module(handlers_mod_name)
    importlib.reload(handlers_mod)

    try:
        events_pkg_mod = importlib.import_module(package_events_mod_name)
        importlib.reload(events_pkg_mod)
    except Exception:
        events_pkg_mod = None

    # Сохраняем оригинал (если есть)
    real = getattr(handlers_mod, event_handler_name)

    async def wrapper(event):
        try:
            # вызываем оригинал
            return await real(event)
        finally:
            # всегда сигналим тесту, даже если оригинал упал
            try:
                ev.set()
            except Exception:
                logger = get_logger(__name__)
                logger.error("TEST-WRAPPER: failed to set processed_event")

    # Патчим реализацию
    monkeypatch.setattr(handlers_mod, event_handler_name, wrapper)

    # Патчим package alias, если он есть
    if events_pkg_mod is not None and hasattr(events_pkg_mod, event_handler_name):
        monkeypatch.setattr(events_pkg_mod, event_handler_name, wrapper)

    # Патчим ссылку прямо в consumer-модуле, если он уже импортирован
    # Это важно: consumer может держать ссылку в своей глобальной переменной.
    try:
        consumer_mod = importlib.import_module(consumer_mod_name)
        # если consumer импортировал имя promo_code_event_handler, заменим его там
        if hasattr(consumer_mod, event_handler_name):
            monkeypatch.setattr(consumer_mod, event_handler_name, wrapper)
    except ModuleNotFoundError:
        # consumer ещё не импортирован — всё ок, патч для него сделаем когда он импортируется
        consumer_mod = None

    # Возвращаем event чтобы тест мог ждать именно его
    return ev

@pytest_asyncio.fixture
async def processed_promo_code(monkeypatch):
    """Определяет точный момент когда закончится обработка события"""
    ev = monkeypatch_event_db(
        monkeypatch,
        "src.services.database.discounts.events.event_handlers_promo_code",
        "src.services.database.discounts.events",
        "promo_code_event_handler"
    )
    yield ev

@pytest_asyncio.fixture
async def processed_voucher(monkeypatch):
    """Определяет точный момент когда закончится обработка события"""
    ev = monkeypatch_event_db(
        monkeypatch,
        "src.services.database.discounts.events.event_handlers_voucher",
        "src.services.database.discounts.events",
        "voucher_event_handler"
    )
    yield ev

@pytest_asyncio.fixture
async def processed_referrals(monkeypatch):
    """Определяет точный момент когда закончится обработка события"""
    ev = monkeypatch_event_db(
        monkeypatch,
        "src.services.database.referrals.events.event_handlers_ref",
        "src.services.database.referrals.events.",
        "referral_event_handler"
    )
    yield ev


@pytest_asyncio.fixture
async def processed_replenishment(monkeypatch):
    """Определяет точный момент когда закончится обработка события"""
    ev = monkeypatch_event_db(
        monkeypatch,
        "src.services.database.replenishments_event.event_handlers_replenishments",
        "src.services.database.replenishments_event.",
        "replenishment_event_handler"
    )
    yield ev