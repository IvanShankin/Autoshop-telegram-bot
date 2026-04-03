from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_config


@asynccontextmanager
async def get_db() -> AsyncSession:
    async_session_factory = get_config().db_connection.session_local
    async with async_session_factory() as session:
        yield session


def get_session_factory() -> AsyncSession:
    return get_config().db_connection.session_local