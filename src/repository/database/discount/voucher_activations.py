from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from src.database.models.discount import VoucherActivations
from src.read_models.other import VoucherActivationsDTO
from src.repository.database.base import DatabaseBase


class VoucherActivationsRepository(DatabaseBase):

    async def get_by_id(
        self,
        voucher_activation_id: int,
    ) -> Optional[VoucherActivationsDTO]:
        stmt = select(VoucherActivations).where(
            VoucherActivations.voucher_activation_id == voucher_activation_id
        )
        result = await self.session_db.execute(stmt)
        activation = result.scalar_one_or_none()
        return VoucherActivationsDTO.model_validate(activation) if activation else None

    async def get_by_voucher_and_user(
        self,
        *,
        voucher_id: int,
        user_id: int,
        for_update: bool = False,
    ) -> Optional[VoucherActivationsDTO]:
        stmt = select(VoucherActivations).where(
            VoucherActivations.voucher_id == voucher_id,
            VoucherActivations.user_id == user_id,
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session_db.execute(stmt)
        activation = result.scalar_one_or_none()
        return VoucherActivationsDTO.model_validate(activation) if activation else None

    async def exists(
        self,
        *,
        voucher_id: int,
        user_id: int,
    ) -> bool:
        stmt = select(VoucherActivations).where(
            VoucherActivations.voucher_id == voucher_id,
            VoucherActivations.user_id == user_id,
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_activation(self, **values) -> VoucherActivationsDTO:
        created = await super().create(VoucherActivations, **values)
        return VoucherActivationsDTO.model_validate(created)
