from src.database.models.admins import (
    AdminActions,
)
from src.read_models import AdminActionsDTO
from src.repository.database.base import DatabaseBase


class AdminActionsRepository(DatabaseBase):

    async def add_admin_action(
        self,
        user_id: int,
        action_type: str,
        message: str,
        details: dict,
    ) -> AdminActionsDTO:
        action = AdminActions(
            user_id=user_id,
            action_type=action_type,
            message=message,
            details=details,
        )
        self.session_db.add(action)
        await self.session_db.flush()
        return AdminActionsDTO.model_validate(action)