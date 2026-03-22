from typing import Optional

from sqlalchemy import select

from src.database.models.users import (
    TransferMoneys,
)
from src.repository.database.base import DatabaseBase


class TransferMoneysRepository(DatabaseBase):
    async def get_by_id(self, transfer_money_id: int) -> Optional[TransferMoneys]:
        result = await self.session_db.execute(
            select(TransferMoneys).where(TransferMoneys.transfer_money_id == transfer_money_id)
        )
        return result.scalar_one_or_none()

    async def create_transfer(self, **values) -> TransferMoneys:
        return await super().create(TransferMoneys, **values)