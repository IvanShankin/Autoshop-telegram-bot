import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from contextlib import asynccontextmanager


load_dotenv()  # Загружает переменные из .env
DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

# URL для подключения к серверу PostgreSQL без указания конкретной базы данных
POSTGRES_SERVER_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/postgres'
# postgresql+asyncpg это означает, что БД работает в асинхронном режиме
SQL_DB_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'

engine_for_create = create_async_engine(SQL_DB_URL)

engine = create_async_engine(SQL_DB_URL)
session_local = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


@asynccontextmanager
async def get_db()->AsyncSession:
    async with session_local() as session:
        yield session