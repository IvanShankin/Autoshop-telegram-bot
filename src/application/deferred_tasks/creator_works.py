from collections.abc import Callable
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.containers import RequestContainer
from src.application.deferred_tasks.jobs import deactivate_discounts_job, dollar_rate_job


class InitScheduler:

    def __init__(
        self,
        scheduler: AsyncIOScheduler,
        container_factory: Callable[[], AsyncGenerator[RequestContainer, None]]
    ):
        self.container_factory = container_factory

        scheduler.add_job(
            deactivate_discounts_job,
            "interval",
            seconds=60,
            args=[container_factory],
        )

        scheduler.add_job(
            dollar_rate_job,
            "interval",
            seconds=3600, # час
            args=[container_factory],
        )