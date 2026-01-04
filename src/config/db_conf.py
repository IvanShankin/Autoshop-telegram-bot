from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


class DbConnectionSettings(BaseModel):
    postgres_server_url: str
    sql_db_url: str
    engine: AsyncEngine
    session_local: sessionmaker


    model_config = ConfigDict(
        arbitrary_types_allowed=True  # Разрешаем произвольные типы
    )

    @classmethod
    def create(cls, db_user: str, db_password: str, db_host: str, db_name: str) -> "DbConnectionSettings":
        # postgresql+asyncpg это означает, что БД работает в асинхронном режиме
        sql_db_url = f'postgresql+asyncpg://{db_user}:{db_password}@{db_host}/{db_name}'
        engine = create_async_engine(sql_db_url)
        return cls(
            # URL для подключения к серверу PostgreSQL без указания конкретной базы данных
            postgres_server_url=f'postgresql+asyncpg://{db_user}:{db_password}@{db_host}/postgres',

            sql_db_url=sql_db_url,
            engine=engine,
            session_local = sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )

        )