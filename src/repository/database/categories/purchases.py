from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.database.models.categories import Purchases
from src.models.read_models import PurchasesDTO
from src.repository.database.base import DatabaseBase


class PurchasesRepository(DatabaseBase):

    async def get_by_id(self, purchase_id: int) -> Optional[PurchasesDTO]:
        result = await self.session_db.execute(
            select(Purchases).where(Purchases.purchase_id == purchase_id)
        )
        purchase = result.scalar_one_or_none()
        return PurchasesDTO.model_validate(purchase) if purchase else None
