from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.database.models.categories import Purchases
from src.repository.database.base import DatabaseBase


class PurchasesRepository(DatabaseBase):

    async def get_by_id(self, purchase_id: int) -> Optional[Purchases]:
        result = await self.session_db.execute(
            select(Purchases).where(Purchases.purchase_id == purchase_id)
        )
        return result.scalar_one_or_none()
