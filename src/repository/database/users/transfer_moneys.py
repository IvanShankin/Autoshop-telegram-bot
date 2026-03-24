from typing import Optional

from sqlalchemy import select

from src.database.models.users import (
    TransferMoneys,
)
from src.read_models.other import TransferMoneysDTO
from src.repository.database.base import DatabaseBase


class TransferMoneysRepository(DatabaseBase):
    async def get_by_id(self, transfer_money_id: int) -> Optional[TransferMoneysDTO]:
        result = await self.session_db.execute(
            select(TransferMoneys).where(TransferMoneys.transfer_money_id == transfer_money_id)
        )
        transfer = result.scalar_one_or_none()
        return TransferMoneysDTO.model_validate(transfer) if transfer else None

    async def create_transfer(self, **values) -> TransferMoneysDTO:
        created = await super().create(TransferMoneys, **values)
        return TransferMoneysDTO.model_validate(created)
