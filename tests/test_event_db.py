import asyncio
import contextlib
from datetime import datetime

import orjson
import pytest
import pytest_asyncio
from dateutil.parser import parse
from sqlalchemy import select

from src.database.core_models import Replenishments, Users, WalletTransaction, UserAuditLogs
from src.database.database import get_db
from src.database.events.core_event import event_queue
from src.modules.referrals.database.events.schemas import NewIncomeFromRef
from src.modules.referrals.database.models import IncomeFromReferrals, Referrals
from src.redis_dependencies.core_redis import get_redis
from tests.fixtures.helper_fixture import create_new_user, create_type_payment, create_referral, create_replenishment
from tests.fixtures.monkeypatch_data import replacement_fake_bot, replacement_fake_keyboard
from tests.fixtures.helper_functions import comparison_models

@pytest_asyncio.fixture
async def start_event_handler():
    # данный импорт обязательно тут, ибо aiogram запустит свой even_loop который не даст работать тесту в режиме отладки
    from src.database.events.triggers_processing import run_triggers_processing

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
async def test_handler_new_replenishment(
        replacement_fake_bot,
        replacement_fake_keyboard,
        create_new_user,
        create_type_payment,
        start_event_handler,
):
    # Исходные данные пользователя
    initial_balance = create_new_user.balance
    initial_total_sum = create_new_user.total_sum_replenishment
    user_id = create_new_user.user_id

    async with get_db() as session_db:
        new_replenishment = Replenishments(
            user_id = create_new_user.user_id,
            type_payment_id = create_type_payment['type_payment_id'],
            origin_amount = 100,
            amount = 105,
            status = 'pending'
        )
        session_db.add(new_replenishment)
        await session_db.commit()
        await session_db.refresh(new_replenishment)

        # Меняем статус на processing (это должно запустить обработчик)
        result_db = await session_db.execute(select(Replenishments).where(Replenishments.replenishment_id == new_replenishment.replenishment_id))
        replenishment = result_db.scalar_one_or_none()
        replenishment.status='processing'

        await session_db.commit()

    q = event_queue
    await asyncio.sleep(0) # для передачи управления
    await q.join() # дождёмся пока очередь событий выполнится

    async with get_db() as session_db:
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

    await comparison_models(updated_user, result_redis)


@pytest.mark.asyncio
async def test_handler_new_income_referral(
    create_new_user,
    create_referral,
    create_replenishment,
    start_event_handler,
    clean_db,
    replacement_fake_bot,
    replacement_fake_keyboard
):
    """Проверяем корректную работу handler_new_income_referral"""
    owner = create_new_user
    referral = create_referral
    replenishment = create_replenishment

    initial_balance = owner.balance
    initial_total_profit = owner.total_profit_from_referrals

    # --- создаём событие ---
    event = NewIncomeFromRef(
        replenishment_id=replenishment.replenishment_id,
        owner_id=owner.user_id,
        referral_id=referral.referral_id,
        amount=replenishment.origin_amount,
        total_sum_replenishment=replenishment.origin_amount,
    )

    q = event_queue  # зафиксировали ссылку один раз
    q.put_nowait(event)

    # ждём пока событие обработается
    await asyncio.sleep(0)
    await q.join()

    async with get_db() as session_db:
        # проверка пользователя (владельца реферала)
        user_result = await session_db.execute(
            select(Users).where(Users.user_id == owner.user_id)
        )
        updated_user = user_result.scalar_one()

        assert updated_user.balance > initial_balance, "Баланс не увеличился"
        assert updated_user.total_profit_from_referrals > initial_total_profit, "Суммарная прибыль от рефералов не обновилась"

        # проверка уровня в Referrals
        referral_result = await session_db.execute(
            select(Referrals).where(Referrals.referral_id == referral.referral_id)
        )
        updated_ref = referral_result.scalar_one()
        assert updated_ref.level >= 0, "Уровень реферала не обновился"

        # проверка IncomeFromReferrals
        income_result = await session_db.execute(
            select(IncomeFromReferrals)
            .where(IncomeFromReferrals.owner_user_id == owner.user_id)
        )
        income = income_result.scalars().first()
        assert income.amount > 0, "Запись о доходе от рефералов не создана"
        assert income.percentage_of_replenishment > 0, "Процент не сохранился"

        # проверка WalletTransaction
        wallet_result = await session_db.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == owner.user_id)
        )
        wallet_trans = wallet_result.scalars().first()
        assert wallet_trans.type == "referral", "Неверный тип транзакции"
        assert wallet_trans.amount == income.amount, "Сумма транзакции не совпадает"
        assert wallet_trans.balance_after == updated_user.balance, "Баланс после транзакции некорректен"

        # проверка UserAuditLogs
        log_result = await session_db.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == owner.user_id)
        )
        log = log_result.scalars().first()
        assert log.action_type == "profit from referral", "Неверный action_type в логах"

    # проверка Redis
    async with get_redis() as session_redis:
        redis_data = orjson.loads(await session_redis.get(f"user:{owner.user_id}"))

    await comparison_models(updated_user, redis_data)

