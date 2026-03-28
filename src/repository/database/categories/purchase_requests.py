from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.database.models.categories import PurchaseRequests
from src.models.read_models import PurchaseRequestsDTO
from src.repository.database.base import DatabaseBase


class PurchaseRequestsRepository(DatabaseBase):

    async def get_by_id(self, purchase_request_id: int) -> Optional[PurchaseRequestsDTO]:
        result = await self.session_db.execute(
            select(PurchaseRequests).where(PurchaseRequests.purchase_request_id == purchase_request_id)
        )
        item = result.scalar_one_or_none()
        return PurchaseRequestsDTO.model_validate(item) if item else None

    async def get_by_id_with_balance_holder(self, purchase_request_id: int) -> Optional[PurchaseRequests]:
        result = await self.session_db.execute(
            select(PurchaseRequests)
            .options(selectinload(PurchaseRequests.balance_holder))
            .where(PurchaseRequests.purchase_request_id == purchase_request_id)
        )
        return result.scalar_one_or_none()

    async def create_request(
        self,
        user_id: int,
        promo_code_id: int | None,
        quantity: int,
        total_amount: int,
        status: str = "processing",
    ) -> PurchaseRequestsDTO:
        created = await super().create(
            PurchaseRequests,
            user_id=user_id,
            promo_code_id=promo_code_id,
            quantity=quantity,
            total_amount=total_amount,
            status=status,
        )
        return PurchaseRequestsDTO.model_validate(created)

    async def update_status(self, purchase_request_id: int, status: str) -> None:
        await self.session_db.execute(
            update(PurchaseRequests)
            .where(PurchaseRequests.purchase_request_id == purchase_request_id)
            .values(status=status)
        )
