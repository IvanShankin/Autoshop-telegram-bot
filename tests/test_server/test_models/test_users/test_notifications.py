import pytest
from sqlalchemy import delete, select

from src.database.models.users import NotificationSettings
from src.models.update_models import UpdateNotificationSettingDTO


class TestNotificationSettingsService:

    @pytest.mark.asyncio
    async def test_create_and_get_notification(
        self,
        session_db_fix,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()

        await session_db_fix.execute(
            delete(NotificationSettings).where(NotificationSettings.user_id == user.user_id)
        )
        await session_db_fix.commit()

        created = await container_fix.notification_service.create_notification(
            user_id=user.user_id,
            make_commit=True,
        )

        assert created.user_id == user.user_id

        result = await session_db_fix.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.user_id)
        )
        db_settings = result.scalar_one()
        assert db_settings.notification_setting_id == created.notification_setting_id

        fetched = await container_fix.notification_service.get_notification(user.user_id)
        assert fetched is not None
        assert fetched.user_id == user.user_id

    @pytest.mark.asyncio
    async def test_update_notifications_updates_db(
        self,
        session_db_fix,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()

        payload = UpdateNotificationSettingDTO(
            referral_invitation=False,
            referral_replenishment=False,
        )

        updated = await container_fix.notification_service.update_notifications(
            user_id=user.user_id,
            data=payload,
        )

        assert updated is not None
        assert updated.referral_invitation is False
        assert updated.referral_replenishment is False

        result = await session_db_fix.execute(
            select(NotificationSettings).where(NotificationSettings.user_id == user.user_id)
        )
        db_settings = result.scalar_one()
        assert db_settings.referral_invitation is False
        assert db_settings.referral_replenishment is False
