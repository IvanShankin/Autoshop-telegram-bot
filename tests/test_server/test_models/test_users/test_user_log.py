import pytest
from sqlalchemy import select

from src.database.models.users import UserAuditLogs
from src.models.create_models.users import CreateUserAuditLogDTO


class TestUserLogService:

    @pytest.mark.asyncio
    async def test_create_log_persists_record(
        self,
        session_db_fix,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()
        payload = CreateUserAuditLogDTO(
            action_type="test.action",
            message="created log entry",
            details={"stage": "unit-test"},
        )

        log = await container_fix.user_log_service.create_log(
            user_id=user.user_id,
            data=payload,
            make_commit=True,
        )

        assert log.user_id == user.user_id
        assert log.action_type == payload.action_type
        assert log.details == payload.details

        result = await session_db_fix.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id)
        )
        db_log = result.scalar_one()
        assert db_log.message == payload.message

    @pytest.mark.asyncio
    async def test_get_all_by_user_returns_logs(
        self,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user()

        first_payload = CreateUserAuditLogDTO(
            action_type="first",
            message="first log",
        )
        second_payload = CreateUserAuditLogDTO(
            action_type="second",
            message="second log",
        )

        await container_fix.user_log_service.create_log(
            user_id=user.user_id,
            data=first_payload,
            make_commit=True,
        )
        await container_fix.user_log_service.create_log(
            user_id=user.user_id,
            data=second_payload,
            make_commit=True,
        )

        logs = await container_fix.user_log_service.get_all_by_user(user.user_id)
        assert len(logs) == 2
        assert {log.action_type for log in logs} == {"first", "second"}
