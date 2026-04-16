from typing import Callable, AsyncGenerator

from src.containers import RequestContainer


async def deactivate_discounts_job(container_factory: Callable[[], AsyncGenerator[RequestContainer, None]]):
    async for container in container_factory():
        use_case = container.get_remove_invalid_discount_use_case()
        await use_case.execute()


async def dollar_rate_job(container_factory: Callable[[], AsyncGenerator[RequestContainer, None]]):
    async for container in container_factory():
        await container.update_dollar_rate_use_case.execute()