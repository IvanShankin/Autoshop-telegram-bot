from __future__ import annotations

from typing import Optional

from sqlalchemy import select, delete

from src.database.models.categories import Purchases
from src.models.read_models import PurchasesDTO
from src.repository.database.base import DatabaseBase


class PurchasesRepository(DatabaseBase):

    async def get_by_id(self, purchase_id: int) -> Optional[PurchasesDTO]:
        result = await self.session_db.execute(
            select(Purchases).where(Purchases.purchase_id == purchase_id)
        )
        purchase = result.scalar_one_or_none()
        return PurchasesDTO.model_validate(purchase, from_attributes=True) if purchase else None

    async def create_purchase(self, **values) -> PurchasesDTO:
        created = await super().create(Purchases, **values)
        return PurchasesDTO.model_validate(created, from_attributes=True)

    async def delete_by_ids(self, purchase_ids: list[int]) -> None:
        if not purchase_ids:
            return
        await self.session_db.execute(
            delete(Purchases).where(Purchases.purchase_id.in_(purchase_ids))
        )
