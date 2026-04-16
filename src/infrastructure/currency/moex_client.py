from logging import Logger

import aiohttp

URL_MOEX_TOD = "https://iss.moex.com/iss/engines/currency/markets/selt/boards/CETS/securities/USD000000TOD.json"
URL_MOEX_INDICATIVE = "https://iss.moex.com/iss/statistics/engines/futures/markets/indicativerates/securities.json?securities=USDRUBF"


class MoexClient:

    def __init__(self, session: aiohttp.ClientSession, logger: Logger):
        self.session = session
        self.logger = logger

    async def get_tod_rate(self) -> float | None:
        try:
            async with self.session.get(URL_MOEX_TOD, timeout=8) as resp:
                data = await resp.json()

                marketdata = data.get("marketdata", {})
                columns = marketdata.get("columns", [])
                values = marketdata.get("data", [])

                if not values:
                    return None

                row = values[0]

                if "LAST" in columns:
                    val = row[columns.index("LAST")]
                    if val:
                        return float(val)

                if "WAPRICE" in columns:
                    val = row[columns.index("WAPRICE")]
                    if val:
                        return float(val)

        except Exception as e:
            self.logger.exception("MOEX TOD error: %s", e)

        return None

    async def get_indicative_rate(self) -> float | None:
        try:
            async with self.session.get(URL_MOEX_INDICATIVE, timeout=8) as resp:
                data = await resp.json()

                securities = data.get("securities", {})
                columns = securities.get("columns", [])
                rows = securities.get("data", [])

                if not rows:
                    return None

                rate_idx = columns.index("rate")
                secid_idx = columns.index("secid")
                clearing_idx = columns.index("clearing")

                for row in reversed(rows):
                    if row[secid_idx] == "USD/RUB" and row[clearing_idx] == "vk":
                        return float(row[rate_idx])

        except Exception as e:
            self.logger.exception("MOEX indicative error: %s", e)

        return None