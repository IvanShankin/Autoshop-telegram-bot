from typing import Optional, Sequence

from sqlalchemy import select, update

from src.database.models.system import TypePayments
from src.repository.database.base import DatabaseBase


class TypePaymentsRepository(DatabaseBase):

    async def get_all(self) -> Sequence[TypePayments]:
        result = await self.session_db.execute(
            select(TypePayments).order_by(TypePayments.index.asc())
        )
        return result.scalars().all()

    async def get_by_id(self, type_payment_id: int) -> Optional[TypePayments]:
        result = await self.session_db.execute(
            select(TypePayments).where(TypePayments.type_payment_id == type_payment_id)
        )
        return result.scalar_one_or_none()

    async def create_type_payment(self, **values) -> TypePayments:
        return await super().create(TypePayments, **values)

    async def update(self, type_payment_id: int, **values) -> Optional[TypePayments]:
        if not values:
            return await self.get_by_id(type_payment_id)

        stmt = (
            update(TypePayments)
            .where(TypePayments.type_payment_id == type_payment_id)
            .values(**values)
            .returning(TypePayments)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def shift_indexes_left(self, new_index: int, old_index: int) -> None:
        await self.session_db.execute(
            update(TypePayments)
            .where(TypePayments.index >= new_index)
            .where(TypePayments.index < old_index)
            .values(index=TypePayments.index + 1)
        )

    async def shift_indexes_right(self, new_index: int, old_index: int) -> None:
        await self.session_db.execute(
            update(TypePayments)
            .where(TypePayments.index <= new_index)
            .where(TypePayments.index > old_index)
            .values(index=TypePayments.index - 1)
        )