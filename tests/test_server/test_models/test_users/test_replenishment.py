import pytest
from sqlalchemy import select

from helpers.helper_functions import comparison_models
from src.database.models.users import Replenishments, WalletTransaction, UserAuditLogs
from src.models.create_models.users import CreateReplenishmentDTO
from src.models.read_models.events.replenishments import NewReplenishment
from src.models.update_models.users import UpdateReplenishment


class TestReplenishmentsService:

    @pytest.mark.asyncio
    async def test_get_replenishment(self, container_fix, create_replenishment):
        replenishment = await create_replenishment(amount=100)
        replenishment_res = await container_fix.replenishment_service.get_replenishment(replenishment.replenishment_id)

        assert comparison_models(replenishment, replenishment_res)

    @pytest.mark.asyncio
    async def test_create_replenishment(self, session_db_fix, container_fix, create_new_user, create_type_payment):
        user = await create_new_user()
        type_payment = await create_type_payment()

        replenishment = await container_fix.replenishment_service.create_replenishment(
            user_id=user.user_id,
            type_payment_id=type_payment.type_payment_id,
            data=CreateReplenishmentDTO(
                origin_amount=100,
                amount=105
            ),
            make_commit=True
        )

        result = await session_db_fix.execute(
            select(Replenishments)
            .where(Replenishments.replenishment_id == replenishment.replenishment_id)
        )
        replenishment_db = result.scalar_one()

        assert comparison_models(replenishment, replenishment_db)

    @pytest.mark.asyncio
    async def test_update_replenishment(self, session_db_fix, container_fix, create_replenishment):
        replenishment = await create_replenishment(amount=100)

        replenishment = await container_fix.replenishment_service.update_replenishment(
            replenishment_id=replenishment.replenishment_id,
            data=UpdateReplenishment(
                status='pending',
                payment_system_id="ID",
                invoice_url="URL",
            ),
            make_commit=True
        )

        result = await session_db_fix.execute(
            select(Replenishments)
            .where(Replenishments.replenishment_id == replenishment.replenishment_id)
        )
        replenishment_db = result.scalar_one()

        assert comparison_models(replenishment, replenishment_db)

    @pytest.mark.asyncio
    async def test_process_new_replenishment_successfully(self, session_db_fix, container_fix, create_replenishment):
        replenishment = await create_replenishment(amount=100, status="processing")

        await container_fix.replenishment_service.process_new_replenishment(
            data=NewReplenishment(
                replenishment_id=replenishment.replenishment_id,
                user_id=replenishment.user_id,
                origin_amount=replenishment.origin_amount,
                amount=replenishment.amount
            ),
        )

        result = await session_db_fix.execute(
            select(Replenishments)
            .where(Replenishments.replenishment_id == replenishment.replenishment_id)
        )
        replenishment_db: Replenishments = result.scalar_one()
        assert replenishment_db.status == "completed"

        result_db = await session_db_fix.execute(select(WalletTransaction).where(WalletTransaction.user_id == replenishment.user_id))
        assert result_db.scalar_one_or_none()

        result_db = await session_db_fix.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == replenishment.user_id))
        assert result_db.scalar_one_or_none()

    @pytest.mark.asyncio
    async def test_process_new_replenishment_unsuccessfully(self, session_db_fix, container_fix, create_replenishment):
        replenishment = await create_replenishment(amount=100, status="processing")

        async def fake_error():
            raise Exception("Fake Error")

        container_fix.wallet_transaction_service.create_wallet_transaction = fake_error

        await container_fix.replenishment_service.process_new_replenishment(
            data=NewReplenishment(
                replenishment_id=replenishment.replenishment_id,
                user_id=replenishment.user_id,
                origin_amount=replenishment.origin_amount,
                amount=replenishment.amount
            ),
        )

        result = await session_db_fix.execute(
            select(Replenishments)
            .where(Replenishments.replenishment_id == replenishment.replenishment_id)
        )
        replenishment_db: Replenishments = result.scalar_one()
        assert replenishment_db.status == "error"

        result_db = await session_db_fix.execute(select(WalletTransaction).where(WalletTransaction.user_id == replenishment.user_id))
        assert not result_db.scalar_one_or_none()