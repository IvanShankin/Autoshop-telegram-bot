from contextlib import asynccontextmanager

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

from src.config import get_config

Base_sqlalchemy = declarative_base()

class Base(Base_sqlalchemy):
    __abstract__ = True  # указывает что класс не будет таблицей

    def to_dict(self):
        """преобразует в словарь все колонки у выбранного объекта"""
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


@asynccontextmanager
async def get_db() -> AsyncSession:
    async_session_factory = get_config().db_connection.session_local
    async with async_session_factory() as session:
        yield session
