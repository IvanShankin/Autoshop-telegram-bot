from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update

from src.database.models.users import BalanceHolder
from src.repository.database.base import DatabaseBase


class BalanceHolderRepository(DatabaseBase):

    async def get_by_request_id(self, purchase_request_id: int) -> Optional[BalanceHolder]:
        result = await self.session_db.execute(
            select(BalanceHolder).where(BalanceHolder.purchase_request_id == purchase_request_id)
        )
        return result.scalar_one_or_none()

    async def create_holder(
        self,
        purchase_request_id: int,
        user_id: int,
        amount: int,
        status: str = "held",
    ) -> BalanceHolder:
        created = await super().create(
            BalanceHolder,
            purchase_request_id=purchase_request_id,
            user_id=user_id,
            amount=amount,
            status=status,
        )
        return created

    async def update_status_by_request_id(self, purchase_request_id: int, status: str) -> None:
        await self.session_db.execute(
            update(BalanceHolder)
            .where(BalanceHolder.purchase_request_id == purchase_request_id)
            .values(status=status)
        )
