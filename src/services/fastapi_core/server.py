import uvicorn
from fastapi import FastAPI
from src.services.payments.crypto_bot.webhook import router as crypto_bot_router

app = FastAPI()
app.include_router(crypto_bot_router)

async def start_server():
    """Запуск FastAPI-сервера в asyncio-задаче"""
    config = uvicorn.Config(app, host="0.0.0.0", port=9119, reload=False)
    server = uvicorn.Server(config)
    await server.serve()