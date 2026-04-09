from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.system import TypePayments
from src.models.read_models.other import TypePaymentsDTO
from src.models.update_models.system import UpdateTypePaymentDTO
from src.repository.database.systems import TypePaymentsRepository
from src.repository.redis import TypePaymentsCacheRepository


class TypesPaymentsService:

    def __init__(
        self,
        type_payment_repo: TypePaymentsRepository,
        cache_repo: TypePaymentsCacheRepository,
        session_db: AsyncSession,
    ):
        self.type_payment_repo = type_payment_repo
        self.cache_repo = cache_repo
        self.session_db = session_db

    async def get_all_types_payments(self) -> Sequence[TypePaymentsDTO]:
        cached = await self.cache_repo.get_all()
        if cached:
            return cached

        items = await self.type_payment_repo.get_all()
        if items:
            await self.cache_repo.set_all(list(items))
        return items

    async def get_type_payment(self, type_payment_id: int) -> Optional[TypePaymentsDTO]:
        cached = await self.cache_repo.get_one(type_payment_id)
        if cached:
            return cached

        item = await self.type_payment_repo.get_by_id(type_payment_id)
        if item:
            await self.cache_repo.set_one(item)
        return item

    async def calculate_replenishment_amount(self, amount: int, type_payment: TypePaymentsDTO) -> int:
        return amount + (amount * type_payment.commission // 100) if type_payment.commission else amount

    async def update_type_payment(
        self,
        type_payment_id: int,
        data: UpdateTypePaymentDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> TypePaymentsDTO:
        type_payment = await self.type_payment_repo.get_by_id(type_payment_id)
        if not type_payment:
            raise ValueError("Тип оплаты не найден")

        values = data.model_dump(exclude_unset=True)

        if "index" in values:
            try:
                new_index = int(values["index"])
            except Exception:
                raise ValueError("index должен быть целым числом")

            if new_index < 0:
                new_index = 0

            total_res = await self.session_db.execute(
                select(func.count()).select_from(TypePayments)
            )
            total_count = total_res.scalar_one()
            max_index = max(0, total_count - 1)

            if new_index > max_index:
                new_index = max_index

            old_index = type_payment.index if type_payment.index is not None else max_index

            if new_index != old_index:
                if new_index < old_index:
                    await self.type_payment_repo.shift_indexes_left(new_index, old_index)
                else:
                    await self.type_payment_repo.shift_indexes_right(new_index, old_index)

                values["index"] = new_index
            else:
                values.pop("index", None)

        updated = await self.type_payment_repo.update(type_payment_id, **values)

        if make_commit:
            await self.session_db.commit()

        if updated and filling_redis:
            items = await self.type_payment_repo.get_all()
            await self.cache_repo.set_all(list(items))
            for item in items:
                await self.cache_repo.set_one(item)

        return updated
