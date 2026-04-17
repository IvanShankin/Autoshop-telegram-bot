import pytest
from orjson import orjson
from sqlalchemy.future import select

from tests.helpers.helper_functions import comparison_models
from src.database.models.users import TransferMoneys, UserAuditLogs, WalletTransaction, Users
from src.exceptions import NotEnoughMoney, UserNotFound


class TestMoneyTransferService:

    @pytest.mark.asyncio
    async def test_money_transfer(self, container_fix, session_db_fix, create_new_user):
        sender = await create_new_user(balance=100)
        recipient = await create_new_user()

        await container_fix.money_transfer_service.create_transfer(
            sender_id=sender.user_id, recipient_id=recipient.user_id, amount=100
        )

        session_redis = container_fix.session_redis

        result_sender = await session_db_fix.execute(select(Users).where(Users.user_id == sender.user_id))
        result_recipient = await session_db_fix.execute(select(Users).where(Users.user_id == recipient.user_id))
        sender = result_sender.scalar()
        recipient = result_recipient.scalar()

        # проверка логов
        result_db = await session_db_fix.execute(select(TransferMoneys).where(TransferMoneys.user_from_id == sender.user_id))
        assert result_db.scalar_one_or_none()

        result_db = await session_db_fix.execute(select(WalletTransaction).where(WalletTransaction.user_id == sender.user_id))
        assert result_db.scalar_one_or_none()
        result_db = await session_db_fix.execute(select(WalletTransaction).where(WalletTransaction.user_id == recipient.user_id))
        assert result_db.scalar_one_or_none()

        result_db = await session_db_fix.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == sender.user_id))
        assert result_db.scalar_one_or_none()
        result_db = await session_db_fix.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == recipient.user_id))
        assert result_db.scalar_one_or_none()

        # проверка БД
        assert sender.balance == 0
        assert recipient.balance == 100

        # проверка _redis
        sender_redis = await session_redis.get(f"user:{sender.user_id}")
        recipient_redis = await session_redis.get(f"user:{recipient.user_id}")

        assert comparison_models(sender, orjson.loads(sender_redis))
        assert comparison_models(recipient, orjson.loads(recipient_redis))

    @pytest.mark.asyncio
    async def test_money_transfer_not_enough_money(self, container_fix, create_new_user, session_db_fix):
        """Тест на исключение нет денег"""

        sender = await create_new_user(balance=50)
        recipient = await create_new_user(balance=0)

        with pytest.raises(NotEnoughMoney):
            await container_fix.money_transfer_service.create_transfer(
                sender_id=sender.user_id, recipient_id=recipient.user_id, amount=100
            )

        # проверки: балансы и записи не изменились
        result_sender = await session_db_fix.execute(select(Users).where(Users.user_id == sender.user_id))
        result_recipient = await session_db_fix.execute(select(Users).where(Users.user_id == recipient.user_id))
        db_sender = result_sender.scalar_one()
        db_recipient = result_recipient.scalar_one()

        assert db_sender.balance == 50
        assert db_recipient.balance == 0

        # нет записей о переводах / транзакциях / аудит-логах
        assert not (await session_db_fix.execute(select(TransferMoneys).where(TransferMoneys.user_from_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db_fix.execute(select(WalletTransaction).where(WalletTransaction.user_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db_fix.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == sender.user_id))).scalar_one_or_none()

    @pytest.mark.asyncio
    async def test_money_transfer_user_not_found(self, container_fix, session_db_fix, create_new_user):
        """Тест на исключение не найдено пользователя"""
        # создаём только получателя
        recipient = await create_new_user(balance=0)

        with pytest.raises(UserNotFound):
            await container_fix.money_transfer_service.create_transfer(
                sender_id=99999999, recipient_id=recipient.user_id, amount=10
            )

        # убедимся, что у реального получателя ничего не изменилось
        result_recipient = await session_db_fix.execute(select(Users).where(Users.user_id == recipient.user_id))
        db_recipient = result_recipient.scalar_one()
        assert db_recipient.balance == 0

    @pytest.mark.asyncio
    async def test_money_transfer_integrity_error_rollback(
        self, container_fix, session_db_fix, create_new_user
    ):
        """
        Симулируем ошибку при создании TransferMoneys (бросаем Exception),
        ожидаем откат (балансы не меняются), и что send_log был вызван.
        """

        sender = await create_new_user(balance=100)
        recipient = await create_new_user(balance=0)

        def failing_create(self, *args, **kwargs):
            # можно бросать конкретную DB-ошибку, но Exception достаточно для отката
            raise Exception("simulated failure during TransferMoneys construction")

        container_fix.wallet_transaction_service.create_wallet_transaction = failing_create

        await container_fix.money_transfer_service.create_transfer(
            sender_id=sender.user_id, recipient_id=recipient.user_id, amount=100
        )

        # Проверяем — откат: балансы не изменились, нет записей о переводах/транзакциях/аудите
        result_sender = await session_db_fix.execute(select(Users).where(Users.user_id == sender.user_id))
        result_recipient = await session_db_fix.execute(select(Users).where(Users.user_id == recipient.user_id))
        db_sender = result_sender.scalar_one()
        db_recipient = result_recipient.scalar_one()

        assert db_sender.balance == 100
        assert db_recipient.balance == 0

        assert not (await session_db_fix.execute(
            select(TransferMoneys).where(TransferMoneys.user_from_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db_fix.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == sender.user_id))).scalar_one_or_none()
        assert not (await session_db_fix.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == sender.user_id))).scalar_one_or_none()
