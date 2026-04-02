from src.exceptions.business import ForbiddenError
from src.services.models.admins import AdminsService


class PermissionService:

    def __init__(
        self,
        admin_service: AdminsService
    ):
        self.admin_service = admin_service

    async def check_permission(self, current_user_id: int, target_user_id: int):
        """
        :except ForbiddenError: Вызовет если `current_user_id` != `target_user_id` и не является админом
        """
        if target_user_id != current_user_id and not await self.admin_service.check_admin(current_user_id):
            raise ForbiddenError()