from logging import Logger

import aiohttp


URL_CBR = "https://www.cbr-xml-daily.ru/daily_json.js"


class CBRClient:

    def __init__(self, session: aiohttp.ClientSession, logger: Logger):
        self.session = session
        self.logger = logger

    async def get_rate(self) -> float | None:
        try:
            async with self.session.get(URL_CBR, timeout=8) as resp:
                data = await resp.json(content_type=None)

                usd = data.get("Valute", {}).get("USD")
                if usd:
                    return float(usd["Value"])


        except Exception as e:
            self.logger.exception("CBR error: %s", e)

        return None