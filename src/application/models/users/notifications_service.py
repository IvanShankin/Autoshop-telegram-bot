from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.read_models.other import NotificationSettingsDTO
from src.models.update_models import UpdateNotificationSettingDTO
from src.repository.database.users import NotificationSettingsRepository


class NotificationSettingsService:

    def __init__(self,notif_repo: NotificationSettingsRepository, session_db: AsyncSession):
        self.notif_repo = notif_repo
        self.session_db = session_db

    async def create_notification(self, user_id: int, make_commit: Optional[bool] = False) -> NotificationSettingsDTO:
        notif = await self.notif_repo.create_notification_settings(user_id=user_id)
        if make_commit:
            await self.session_db.commit()

        return notif

    async def get_notification(self, user_id: int) -> Optional[NotificationSettingsDTO]:
        return await self.notif_repo.get_by_user_id(user_id)

    async def update_notifications(self, user_id: int, data: UpdateNotificationSettingDTO) -> Optional[NotificationSettingsDTO]:
        values = data.model_dump(exclude_unset=True)
        notif = await self.notif_repo.update(user_id, **values)
        await self.session_db.commit()
        return notif


