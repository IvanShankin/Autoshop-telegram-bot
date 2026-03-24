from typing import Optional

from sqlalchemy import select, update

from src.database.models.users import (
    NotificationSettings,
)
from src.read_models.other import NotificationSettingsDTO
from src.repository.database.base import DatabaseBase


class NotificationSettingsRepository(DatabaseBase):
    async def get_by_user_id(self, user_id: int) -> Optional[NotificationSettingsDTO]:
        result = await self.session_db.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()
        return NotificationSettingsDTO.model_validate(settings) if settings else None

    async def create_notification_settings(self, **values) -> NotificationSettingsDTO:
        created = await super().create(NotificationSettings, **values)
        return NotificationSettingsDTO.model_validate(created)

    async def update(self, user_id: int, **values) -> Optional[NotificationSettingsDTO]:
        if not values:
            return await self.get_by_user_id(user_id)

        stmt = (
            update(NotificationSettings)
            .where(NotificationSettings.user_id == user_id)
            .values(**values)
            .returning(NotificationSettings)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return NotificationSettingsDTO.model_validate(updated) if updated else None
