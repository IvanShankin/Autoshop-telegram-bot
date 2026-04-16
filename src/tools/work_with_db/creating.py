import asyncio

from src.containers.app_container import AppContainer
from src.database.creating import create_database, create_table


async def create():
    """Создает базу данных и все таблицы в ней (если существует, то ничего не произойдёт)"""
    app_container = AppContainer()
    try:
        await create_database(app_container.conf)
        await create_table(app_container.conf)
    finally:
        await app_container.shutdown()

if __name__ == "__main__":
    asyncio.run(create())