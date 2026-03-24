from typing import Optional, Sequence

from sqlalchemy import select, update

from src.database.models.system import TypePayments
from src.read_models.other import TypePaymentsDTO
from src.repository.database.base import DatabaseBase


class TypePaymentsRepository(DatabaseBase):

    async def get_all(self) -> Sequence[TypePaymentsDTO]:
        result = await self.session_db.execute(
            select(TypePayments).order_by(TypePayments.index.asc())
        )
        items = list(result.scalars().all())
        return [TypePaymentsDTO.model_validate(item) for item in items]

    async def get_by_id(self, type_payment_id: int) -> Optional[TypePaymentsDTO]:
        result = await self.session_db.execute(
            select(TypePayments).where(TypePayments.type_payment_id == type_payment_id)
        )
        item = result.scalar_one_or_none()
        return TypePaymentsDTO.model_validate(item) if item else None

    async def create_type_payment(self, **values) -> TypePaymentsDTO:
        created = await super().create(TypePayments, **values)
        return TypePaymentsDTO.model_validate(created)

    async def update(self, type_payment_id: int, **values) -> Optional[TypePaymentsDTO]:
        if not values:
            return await self.get_by_id(type_payment_id)

        stmt = (
            update(TypePayments)
            .where(TypePayments.type_payment_id == type_payment_id)
            .values(**values)
            .returning(TypePayments)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return TypePaymentsDTO.model_validate(updated) if updated else None

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
