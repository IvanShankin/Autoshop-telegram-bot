from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.users import CreateReplenishmentDTO
from src.models.read_models.other import ReplenishmentsDTO
from src.models.update_models.users import UpdateReplenishment
from src.repository.database.replanishments import ReplenishmentsRepository


class ReplenishmentsService:

    def __init__(
        self,
        replenishment_repo: ReplenishmentsRepository,
        session_db: AsyncSession,
    ):
        self.replenishment_repo = replenishment_repo
        self.session_db = session_db

    async def create_replenishment(
        self,
        user_id: int,
        type_payment_id: int,
        data: CreateReplenishmentDTO,
        make_commit: Optional[bool] = False
    ) -> ReplenishmentsDTO:
        """Создает Replenishments в БД. Статус выставляется автоматически 'pending' """
        values = data.model_dump()
        rep = await self.replenishment_repo.create_replenishment(
            user_id=user_id, type_payment_id=type_payment_id, **values
        )

        if make_commit:
            await self.session_db.commit()

        return rep

    async def get_replenishment(
        self,
        replenishment_id: int,
    ) -> ReplenishmentsDTO:
        return await self.replenishment_repo.get_by_id(replenishment_id)

    async def update_replenishment(
        self,
        replenishment_id: int,
        data: UpdateReplenishment,
        make_commit: Optional[bool] = False
    ) -> Optional[ReplenishmentsDTO]:
        values = data.model_dump(exclude_unset=True)
        rep = await self.replenishment_repo.update(replenishment_id, **values)

        if make_commit:
            await self.session_db.commit()

        return rep

