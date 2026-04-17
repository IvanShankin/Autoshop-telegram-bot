from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_config


def get_session_factory() -> AsyncSession:
    return get_config().db_connection.session_local()