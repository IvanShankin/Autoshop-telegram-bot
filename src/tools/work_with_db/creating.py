import asyncio

from src.config import Config
from src.containers.app_container import AppContainer
from src.database.creating import create_database, create_table


async def create(conf: Config):
    """Создает базу данных и все таблицы в ней (если существует, то ничего не произойдёт)"""
    await create_database(conf)
    await create_table(conf)


if __name__ == "__main__":
    app_container = AppContainer()
    asyncio.run(create(app_container.conf))