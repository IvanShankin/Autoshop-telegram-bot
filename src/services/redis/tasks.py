import asyncio
import json

import aiohttp
import logging

from src.config import get_config
from src.services.redis.core_redis import get_redis

# API-источники
URL_MOEX_TOD = "https://iss.moex.com/iss/engines/currency/markets/selt/boards/CETS/securities/USD000000TOD.json"
URL_MOEX_INDICATIVE = "https://iss.moex.com/iss/statistics/engines/futures/markets/indicativerates/securities.json?securities=USDRUBF"
URL_CBR = "https://www.cbr-xml-daily.ru/daily_json.js"


# Парсеры данных
async def _fetch_moex_tod(session: aiohttp.ClientSession) -> float | None:
    """Получает курс доллара по данным Мосбиржи (spot market, USD000000TOD)."""
    try:
        async with session.get(URL_MOEX_TOD, timeout=8) as resp:
            data = await resp.json()
            marketdata = data.get("marketdata", {})
            columns = marketdata.get("columns", [])
            values = marketdata.get("data", [])

            if not values:
                return None

            # поле LAST или WAPRICE может быть основным
            last_idx = columns.index("LAST") if "LAST" in columns else None
            wap_idx = columns.index("WAPRICE") if "WAPRICE" in columns else None

            row = values[0]
            if last_idx is not None and row[last_idx]:
                return float(row[last_idx])
            if wap_idx is not None and row[wap_idx]:
                return float(row[wap_idx])
    except Exception as e:
        logging.warning(f"Ошибка при получении курса с MOEX_TOD: {e}")
    return None


async def _fetch_moex_indicative(session: aiohttp.ClientSession) -> float | None:
    """Получает курс доллара по данным Мосбиржи (indicativerates)."""
    try:
        async with session.get(URL_MOEX_INDICATIVE, timeout=8) as resp:
            data = await resp.json()
            securities = data.get("securities", {})
            columns = securities.get("columns", [])
            rows = securities.get("data", [])
            if not rows:
                return None

            # Найти последнюю запись для USD/RUB с типом "vk" (вечерний клиринг)
            rate_idx = columns.index("rate") if "rate" in columns else None
            secid_idx = columns.index("secid") if "secid" in columns else None
            clearing_idx = columns.index("clearing") if "clearing" in columns else None

            if None in (rate_idx, secid_idx, clearing_idx):
                return None

            for row in reversed(rows):
                if row[secid_idx] == "USD/RUB" and row[clearing_idx] == "vk":
                    return float(row[rate_idx])
    except Exception as e:
        logging.warning(f"Ошибка при получении курса с MOEX_INDICATIVE: {e}")
    return None


async def _fetch_cbr(session: aiohttp.ClientSession) -> float | None:
    """Получает официальный курс ЦБ РФ."""
    try:
        async with session.get(URL_CBR, timeout=8) as resp:
            text = await resp.text()
            data = json.loads(text)
            usd = data.get("Valute", {}).get("USD", {})
            if usd and "Value" in usd:
                return float(usd["Value"])
    except Exception as e:
        logging.warning(f"Ошибка при получении курса с CBR: {e}")
    return None


# Основная логика
async def _fetch_usd_rub_rate() -> float | None:
    """Пробует получить курс из нескольких источников (по приоритету)."""
    async with aiohttp.ClientSession() as session:
        # Мосбиржа (реальный рынок)
        rate = await _fetch_moex_tod(session)
        if rate:
            return rate

        # Мосбиржа (индикативные котировки)
        rate = await _fetch_moex_indicative(session)
        if rate:
            return rate

        # ЦБ РФ
        rate = await _fetch_cbr(session)
        if rate:
            return rate

        logging.error("Не удалось получить курс доллара ни с одного источника.")
        return None


async def _set_dollar_rate():
    rate = await _fetch_usd_rub_rate()
    if rate:
        logging.info(f"Текущий курс USD/RUB: {rate:.4f}")
        async with get_redis() as session_redis:
            await session_redis.set('dollar_rate', rate)
    else:
        logging.warning("Курс не получен.")


# Планировщик
async def start_dollar_rate_scheduler():
    """Периодический запуск получения курса."""
    while True:
        try:
            await _set_dollar_rate()
        except Exception as e:
            logging.error(f"Ошибка при установление курса: {str(e)}")

        await asyncio.sleep(get_config().different.fetch_interval)
