import uvicorn
from fastapi import FastAPI

from src.containers.app_container import AppContainer
from src.infrastructure.web.api.crypto_bot_webhook import router as crypto_bot_router


app = FastAPI()
app.include_router(crypto_bot_router)


async def start_server(app_container: AppContainer):
    """Запуск FastAPI-сервера в asyncio-задаче"""
    app.state.container = app_container

    config = uvicorn.Config(app, host="0.0.0.0", port=9119, reload=False)
    server = uvicorn.Server(config)

    await server.serve()