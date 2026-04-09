from typing import Sequence, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.admins import CreateAdminAction
from src.models.read_models import AdminActionsDTO
from src.repository.database.admins import AdminActionsRepository


class AdminActionsService:

    def __init__(
        self,
        admin_actions_repo: AdminActionsRepository,
        session_db: AsyncSession
    ):
        self.admin_actions_repo = admin_actions_repo
        self.session_db = session_db

    async def create_admin_action(
        self,
        user_id: int,
        data: CreateAdminAction,
        make_commit: Optional[bool] = False
    ) -> AdminActionsDTO:
        """
        :param user_id: id админа совершившего действие
        """
        action = await self.admin_actions_repo.add_admin_action(user_id=user_id, **(data.model_dump()))
        if make_commit:
            await self.session_db.commit()

        return action

    async def get_all_by_user(self, user_id: int) -> Sequence[AdminActionsDTO]:
        """
        :param user_id: тг id админа
        """
        return await self.admin_actions_repo.get_all_by_user(user_id=user_id)