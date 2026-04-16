import logging
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from src.config import Config
from src.database import Base


async def create_database(conf: Config):
    """Создает базу данных и все таблицы в ней (если существует, то ничего не произойдёт) """
    # Сначала подключаемся к серверу PostgreSQL без указания конкретной базы
    engine = create_async_engine(conf.db_connection.postgres_server_url, isolation_level="AUTOCOMMIT")

    try:
        # Проверяем существование базы данных и создаем если ее нет
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{conf.env.db_name}'")
            )
            database_exists = result.scalar() == 1

            if not database_exists: # если БД нет
                logging.info(f"Creating _database {conf.env.db_name}...")
                await conn.execute(text(f"CREATE DATABASE {conf.env.db_name}"))
                logging.info(f"Database {conf.env.db_name} created successfully")
            else:
                logging.info(f"Database {conf.env.db_name} already exists")
    except Exception as e:
        logging.error(f"Error checking/creating _database: {e}")
        raise
    finally:
        await engine.dispose()

    # создаем таблицы в целевой базе данных
    engine = create_async_engine(conf.db_connection.sql_db_url, connect_args={"statement_cache_size": 0})
    try:
        async with engine.begin() as conn:
            logging.info("Creating _database tables...")
            await conn.run_sync(Base.metadata.create_all)
            logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
        raise
    finally:
        await engine.dispose()


async def create_table(conf: Config):
    """создает таблицы в целевой базе данных"""
    engine = create_async_engine(conf.db_connection.sql_db_url, connect_args={"statement_cache_size": 0})
    try:
        async with engine.begin() as conn:
            logging.info("Creating core tables...")
            await conn.run_sync(Base.metadata.create_all)
            logging.info("Database tables created successfully")
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
        raise
    finally:
        await engine.dispose()
