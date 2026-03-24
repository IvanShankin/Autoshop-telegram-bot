from typing import TypeVar, Type, Optional, Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config


ModelType = TypeVar("ModelType")


class DatabaseBase:

    def __init__(self, session_db: AsyncSession, config: Config):
        self.session_db = session_db
        self.conf = config

    async def create(self, db_model: Type[ModelType], **values) -> ModelType:
        """
        Создаст `db_model` с указанными `**values` и произведёт `flush()`
        :return: Созданная модель
        """
        obj = db_model(**values)
        self.session_db.add(obj)
        await self.session_db.flush()
        return obj


class DataRecipient(DatabaseBase):

    async def get_all(self, model: Type[ModelType], condition: Optional[Any] = None) -> List[ModelType]:
        stmt = select(model)
        if condition:
            stmt = stmt.where(condition)
        result = await self.session_db.execute(stmt)
        return result.scalars().all()