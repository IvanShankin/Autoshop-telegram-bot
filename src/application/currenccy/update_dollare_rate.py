from logging import Logger

from src.infrastructure.currency.cbr_client import CBRClient
from src.infrastructure.currency.moex_client import MoexClient
from src.repository.redis import DollarRateCacheRepository


class UpdateDollarRateUseCase:

    def __init__(
        self,
        moex_client: MoexClient,
        cbr_client: CBRClient,
        dollar_rate_repo: DollarRateCacheRepository,
        logger: Logger,
    ):
        self.moex_client = moex_client
        self.cbr_client = cbr_client
        self.repo = dollar_rate_repo
        self.logger = logger

    async def execute(self) -> float | None:
        # приоритет: MOEX → fallback → CBR

        rate = await self.moex_client.get_tod_rate()
        if not rate:
            rate = await self.moex_client.get_indicative_rate()

        if not rate:
            rate = await self.cbr_client.get_rate()

        if not rate:
            self.logger.error("Не удалось получить курс USD/RUB")
            return None

        await self.repo.set(rate)

        self.logger.info("USD/RUB updated: %.4f", rate)

        return rate