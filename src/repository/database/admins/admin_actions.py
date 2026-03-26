from typing import Sequence

from sqlalchemy import select

from src.database.models.admins import (
    AdminActions,
)
from src.models.read_models import AdminActionsDTO
from src.repository.database.base import DatabaseBase


class AdminActionsRepository(DatabaseBase):

    async def get_all_by_user(self, user_id: int) -> Sequence[AdminActionsDTO]:
        result = await self.session_db.execute(
            select(AdminActions).where(AdminActions.user_id == user_id)
        )
        users = list(result.scalars().all())
        return [AdminActionsDTO.model_validate(user) for user in users]

    async def add_admin_action(
        self,
        **values,
    ) -> AdminActionsDTO:
        created = await super().create(AdminActions, **values)
        return AdminActionsDTO.model_validate(created)