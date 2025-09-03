import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

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

Base_sqlalchemy = declarative_base()
class Base(Base_sqlalchemy):
    __abstract__ = True  # указывает что класс не будет таблицей

    def to_dict(self):
        """преобразует в словарь все колонки у выбранного объекта"""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


@asynccontextmanager
async def get_db()->AsyncSession:
    async with session_local() as session:
        yield session