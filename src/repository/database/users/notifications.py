from typing import Optional

from sqlalchemy import select, update

from src.database.models.users import (
    NotificationSettings,
)
from src.repository.database.base import DatabaseBase


class NotificationSettingsRepository(DatabaseBase):
    async def get_by_user_id(self, user_id: int) -> Optional[NotificationSettings]:
        result = await self.session_db.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_notification_settings(self, **values) -> NotificationSettings:
        return await super().create(NotificationSettings, **values)

    async def update(self, user_id: int, **values) -> Optional[NotificationSettings]:
        if not values:
            return await self.get_by_user_id(user_id)

        stmt = (
            update(NotificationSettings)
            .where(NotificationSettings.user_id == user_id)
            .values(**values)
            .returning(NotificationSettings)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()