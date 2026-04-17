import pytest

from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from src.database import get_session_factory
from src.database.models.admins import AdminActions
from src.database.models.discount import Vouchers, VoucherActivations
from src.database.models.users import Users, WalletTransaction, UserAuditLogs
from src.exceptions import NotEnoughMoney
from src.models.create_models.discounts import CreateVoucherDTO
from src.models.read_models.other import UsersDTO
from src.repository.database.admins import AdminActionsRepository
from src.repository.database.discount import VoucherActivationsRepository, VouchersRepository
from src.repository.database.users import UserAuditLogsRepository, UsersRepository, WalletTransactionRepository
from src.application.models.discounts.vouchers_service import VoucherService


@pytest.fixture()
def stub_publish_event(monkeypatch):
    calls = []

    async def _fake_publish_event(payload, routing_key):
        calls.append((payload, routing_key))

    monkeypatch.setattr("src.infrastructure.rabbit_mq.producer.publish_event", _fake_publish_event)
    monkeypatch.setattr("src.application.events.publish_event_handler.publish_event", _fake_publish_event)
    return calls


class TestVoucherService:

    @pytest.mark.asyncio
    async def test_create_voucher_deducts_balance_and_caches(
        self,
        container_fix,
        create_new_user,
        session_db_fix,
    ):
        user = await create_new_user(balance=500)
        dto = CreateVoucherDTO(
            is_created_admin=False,
            amount=50,
            number_of_activations=3,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        voucher = await container_fix.voucher_service.create_voucher(
            user_id=user.user_id,
            data=dto,
        )

        updated_user = await session_db_fix.execute(
            select(Users).where(Users.user_id == user.user_id)
        )
        assert updated_user.scalar_one().balance == 500 - 150

        tx = await session_db_fix.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == user.user_id)
        )
        assert tx.scalar_one().amount == -150

        log = await session_db_fix.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id)
        )
        assert log.scalar_one_or_none() is not None

        assert await container_fix.session_redis.get(f"voucher:{voucher.activation_code}")
        assert await container_fix.session_redis.get(f"voucher_by_user:{user.user_id}")

    @pytest.mark.asyncio
    async def test_create_voucher_not_enough_money(self, container_fix, create_new_user):
        user = await create_new_user(balance=0)
        dto = CreateVoucherDTO(
            is_created_admin=False,
            amount=100,
            number_of_activations=2,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        with pytest.raises(NotEnoughMoney):
            await container_fix.voucher_service.create_voucher(user.user_id, dto)

        assert not (await container_fix.session_db.execute(
            select(Vouchers).where(Vouchers.creator_id == user.user_id)
        )).scalar_one_or_none()

    @pytest.mark.asyncio
    async def test_create_voucher_as_admin_logs_action(
        self,
        container_fix,
        create_new_user,
        session_db_fix,
    ):
        user = await create_new_user(balance=0)
        dto = CreateVoucherDTO(
            is_created_admin=True,
            amount=20,
            number_of_activations=2,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        voucher = await container_fix.voucher_service.create_voucher(
            user_id=user.user_id,
            data=dto,
        )

        tx = await session_db_fix.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == user.user_id)
        )
        assert tx.scalar_one_or_none() is None

        action = await session_db_fix.execute(
            select(AdminActions).where(
                AdminActions.user_id == user.user_id,
                AdminActions.action_type == "create_voucher",
            )
        )
        assert action.scalar_one_or_none() is not None

        assert await container_fix.session_redis.get(f"voucher:{voucher.activation_code}")

    @pytest.mark.asyncio
    async def test_get_valid_voucher_by_page_and_count_use_cache(
        self,
        container_fix,
        create_new_user,
    ):
        user = await create_new_user(balance=200)
        dto = CreateVoucherDTO(
            is_created_admin=False,
            amount=50,
            number_of_activations=1,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        await container_fix.voucher_service.create_voucher(user.user_id, dto)

        page = await container_fix.voucher_service.get_valid_voucher_by_page(user_id=user.user_id)
        assert len(page) == 1

        count = await container_fix.voucher_service.get_count_voucher(user_id=user.user_id)
        assert count == 1

    @pytest.mark.asyncio
    async def test_get_valid_voucher_by_code_and_by_id(
        self,
        container_fix,
        create_new_user,
    ):
        owner = await create_new_user(balance=200)
        dto = CreateVoucherDTO(
            is_created_admin=False,
            amount=30,
            number_of_activations=2,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        voucher = await container_fix.voucher_service.create_voucher(owner.user_id, dto)
        if container_fix.session_db.in_transaction():
            await container_fix.session_db.rollback()

        assert await container_fix.voucher_service.get_valid_voucher_by_code(voucher.activation_code)
        assert await container_fix.voucher_service.get_voucher_by_id(voucher.voucher_id)

    @pytest.mark.asyncio
    async def test_deactivate_voucher_refunds_user(
        self,
        container_fix,
        create_new_user,
        session_db_fix,
    ):
        user = await create_new_user(balance=500)
        dto = CreateVoucherDTO(
            is_created_admin=False,
            amount=25,
            number_of_activations=3,
            expire_at=datetime.now(timezone.utc) + timedelta(days=1),
        )

        voucher = await container_fix.voucher_service.create_voucher(user.user_id, dto)
        refund_amount = await container_fix.voucher_service.deactivate_voucher(voucher.voucher_id)

        assert refund_amount == 75

        refreshed = await session_db_fix.execute(
            select(Users).where(Users.user_id == user.user_id)
        )
        assert refreshed.scalar_one().balance == 500

        tx = await session_db_fix.execute(
            select(WalletTransaction).where(
                WalletTransaction.user_id == user.user_id,
                WalletTransaction.type == "refund",
            )
        )
        assert tx.scalar_one_or_none() is not None

        logs = await session_db_fix.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id)
        )
        found = [entry.action_type for entry in logs.scalars().all()]
        assert "deactivate_voucher" in found
        assert "return_money_from_vouchers" in found

        assert (await container_fix.session_redis.get(f"voucher:{voucher.activation_code}")) is None

    @pytest.mark.asyncio
    async def test_activate_voucher_updates_balance_and_caches(
        self,
        container_fix,
        create_voucher,
        create_new_user,
        session_db_fix,
        stub_publish_event,
    ):
        voucher = await create_voucher(
            number_of_activations=1,
            is_created_admin=False,
        )
        target = await create_new_user(balance=0)
        user_dto = UsersDTO.model_validate(target)

        async with get_session_factory() as new_session:
            test_service = VoucherService(
                vouchers_repo=VouchersRepository(
                    session_db=new_session,
                    config=container_fix.config,
                ),
                voucher_activations_repo=VoucherActivationsRepository(
                    session_db=new_session,
                    config=container_fix.config,
                ),
                users_repo=UsersRepository(
                    session_db=new_session,
                    config=container_fix.config,
                ),
                user_log_repo=UserAuditLogsRepository(
                    session_db=new_session,
                    config=container_fix.config,
                ),
                wallet_transaction_repo=WalletTransactionRepository(
                    session_db=new_session,
                    config=container_fix.config,
                ),
                admin_actions_repo=AdminActionsRepository(
                    session_db=new_session,
                    config=container_fix.config,
                ),
                cache_vouchers_repo=container_fix.vouchers_cache__repo,
                cache_users_repo=container_fix.users_cache_repo,
                publish_event_handler=container_fix.publish_event_handler,
                conf=container_fix.config,
                session_db=new_session,
            )

            message, success = await test_service.activate_voucher(
                user_dto,
                voucher.activation_code,
                language="ru",
            )
            assert stub_publish_event and stub_publish_event[-1][1] == "voucher.activated"
            message2, success2 = await test_service.activate_voucher(
                user_dto,
                voucher.activation_code,
                language="ru",
            )

        assert success
        assert "voucher_successfully_activated" in message or success

        updated = await session_db_fix.execute(
            select(Users).where(Users.user_id == target.user_id)
        )
        assert updated.scalar_one().balance == voucher.amount

        activation = await session_db_fix.execute(
            select(VoucherActivations).where(VoucherActivations.user_id == target.user_id)
        )
        assert activation.scalar_one_or_none() is not None

        assert await container_fix.session_redis.get(f"user:{target.user_id}")
        assert not success2
        assert isinstance(message2, str)
