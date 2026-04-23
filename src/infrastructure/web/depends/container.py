from typing import AsyncGenerator

from fastapi import Request

from src.containers import RequestContainer
from src.containers.app_container import AppContainer


async def get_container(request: Request) -> AsyncGenerator[RequestContainer, None]:
    app_container: AppContainer = request.app.state.container

    factory = app_container.get_request_container_factory()

    async for container in factory():
        yield container
