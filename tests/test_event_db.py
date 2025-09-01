import asyncio
import contextlib
from datetime import datetime
from dateutil.parser import parse

import orjson
import pytest
import pytest_asyncio
from sqlalchemy import select

from src.database.core_models import Replenishments, Users, WalletTransaction, UserAuditLogs
from src.database.database import get_db
from src.database.events.core_event import event_queue
from src.database.events.triggers_processing import run_triggers_processing
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.halper_fixture import create_new_user, create_type_payment

@pytest_asyncio.fixture
async def start_event_handler():
    task = asyncio.create_task(run_triggers_processing())
    try:
        yield
    finally:
        # ждём пока все тестовые события обработаны
        await event_queue.join()
        # закрываем dispatcher через sentinel
        event_queue.put_nowait(None)
        with contextlib.suppress(asyncio.CancelledError):
            await task

@pytest.mark.asyncio
async def test_handler_new_replenishment(create_new_user, create_type_payment, start_event_handler):
    # Исходные данные пользователя
    initial_balance = create_new_user['balance']
    initial_total_sum = create_new_user['total_sum_replenishment']
    user_id = create_new_user['user_id']

    async with get_db() as session_db:
        new_replenishment = Replenishments(
            user_id = create_new_user['user_id'],
            type_payment_id = create_type_payment['type_payment_id'],
            origin_amount = 100,
            amount = 105,
            status = 'pending'
        )
        session_db.add(new_replenishment)
        await session_db.commit()
        await session_db.refresh(new_replenishment)

        # Меняем статус на completed (это должно запустить обработчик)
        result_db = await session_db.execute(select(Replenishments).where(Replenishments.replenishment_id == new_replenishment.replenishment_id))
        replenishment = result_db.scalar_one_or_none()
        replenishment.status='completed'


        await session_db.commit()

        await asyncio.sleep(0) # для передачи управления в event_loop
        await event_queue.join() # дождёмся пока task_done вызовется

        # Проверяем, что баланс пользователя обновился
        user_result = await session_db.execute(select(Users).where(Users.user_id == user_id))
        updated_user = user_result.scalar_one()

        assert updated_user.balance == initial_balance + 105, "Баланс пользователя не обновился"
        assert updated_user.total_sum_replenishment == initial_total_sum + 105, "Общая сумма пополнений не обновилась"

        # Проверяем создание записи в WalletTransaction
        transaction_result = await session_db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
        )
        wallet_transaction = transaction_result.scalar_one()

        assert wallet_transaction is not None, "Запись в WalletTransaction не создана"
        assert wallet_transaction.type == 'replenish', "Неверный тип транзакции"
        assert wallet_transaction.amount == 105, "Неверная сумма транзакции"
        assert wallet_transaction.balance_before == initial_balance, "Неверный баланс до операции"
        assert wallet_transaction.balance_after == initial_balance + 105, "Неверный баланс после операции"

        # Проверяем создание записи в UserAuditLogs
        log_result = await session_db.execute(
            select(UserAuditLogs)
            .where(UserAuditLogs.user_id == user_id)
        )
        user_log = log_result.scalar_one()

        assert user_log is not None, "Запись в UserAuditLogs не создана"
        assert user_log.action_type == 'replenish', "Неверный тип действия в логах"
        assert user_log.details['amount'] == 105, "Неверная сумма в деталях лога"
        assert user_log.details['new_balance'] == initial_balance + 105, "Неверный новый баланс в деталях лога"

        async with get_redis() as session_redis:
            result_redis = orjson.loads(await session_redis.get(f'user:{updated_user.user_id}'))

        user_dict = updated_user.to_dict()
        for key in user_dict:
            if isinstance(user_dict[key], datetime):# если встретили дата
                assert user_dict[key] == parse(result_redis[key])
            else:
                assert user_dict[key] == result_redis[key]
