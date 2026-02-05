import orjson
import pytest
from sqlalchemy import MetaData, Table
from sqlalchemy import select

from src.broker.producer import publish_event
from src.services.database.core.database import get_db
from src.services.database.replenishments_event.schemas import ReplenishmentFailed, ReplenishmentCompleted, \
    NewReplenishment
from src.services.database.system.actions import update_settings
from src.services.database.users.models import Replenishments, Users, WalletTransaction, UserAuditLogs
from src.services.redis.core_redis import get_redis
from src.utils.i18n import get_text, n_get_text
from tests.test_server.test_events.helpers_fun import wait_until_queue_empty, wait_until
from tests.helpers.helper_functions import comparison_models
from tests.helpers.monkeypatch_data import fake_bot


async def _create_and_update_replenishment(
    user_id: int,
    type_payment_id: int,
) -> Replenishments:
    """
    Запустит событие на обработку нового пополнения и дождётся его выполнения
    :return возвращает созданный Replenishments
    """

    async with get_db() as session_db:
        new_replenishment = Replenishments(
            user_id = user_id,
            type_payment_id = type_payment_id,
            origin_amount = 100,
            amount = 105,
            status = 'processing'
        )
        session_db.add(new_replenishment)
        await session_db.commit()
        await session_db.refresh(new_replenishment)

        event = NewReplenishment(
            replenishment_id=new_replenishment.replenishment_id,
            user_id=new_replenishment.user_id,
            origin_amount=new_replenishment.origin_amount,
            amount=new_replenishment.amount
        )

    return new_replenishment


@pytest.mark.asyncio
async def test_access(
    create_new_user,
    create_replenishment
):
    """Интеграционный тест"""
    from src.services.database.replenishments_event.event_handlers_replenishments import replenishment_event_handler

    user = await create_new_user()

    # Исходные данные пользователя
    initial_balance = user.balance
    initial_total_sum = user.total_sum_replenishment
    user_id = user.user_id

    replenishment = await create_replenishment(amount=105, user_id=user.user_id, status="processing")

    event = NewReplenishment(
        replenishment_id=replenishment.replenishment_id,
        user_id=replenishment.user_id,
        origin_amount=replenishment.origin_amount,
        amount=replenishment.amount
    )
    await replenishment_event_handler({"event": "replenishment.new_replenishment", "payload": event})

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

    assert comparison_models(updated_user, result_redis)

    # проверяем, что ReplenishmentFailed отработал

    # сообщение пользователю
    message_for_user = n_get_text(
        user.language,
        "replenishment",
        "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
        "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
        replenishment.amount
    ).format(sum=replenishment.amount)

    assert fake_bot.get_message(user.user_id, message_for_user)


@pytest.mark.asyncio
async def test_consumer_calls_replenishment_handler(
    start_consumer,
    rabbit_channel,
    get_engine,
    create_new_user,
    create_replenishment,
):
    user = await create_new_user()

    replenishment = await create_replenishment(amount=105, user_id=user.user_id, status="processing")

    event = NewReplenishment(
        replenishment_id=replenishment.replenishment_id,
        user_id=replenishment.user_id,
        origin_amount=replenishment.origin_amount,
        amount=replenishment.amount
    )

    await publish_event(
        event.model_dump(),
        routing_key="replenishment.new_replenishment",
    )

    # ждём ACK
    await wait_until_queue_empty(
        rabbit_channel,
        queue_name="events_db",  # реальное имя очереди
        timeout=5,
    )

    async def replenishment_processed():
        async with get_db() as session:
            result = await session.execute(
                select(Replenishments.status)
                .where(Replenishments.replenishment_id == replenishment.replenishment_id)
            )
            return result.scalar_one() != "processing"

    await wait_until(replenishment_processed, timeout=5)


@pytest.mark.asyncio
async def test_fail(
    get_engine,
    create_new_user,
    create_replenishment,
):
    """
    Интеграционный тест:
    - Пользователь получает сообщение об ошибке
    """
    from src.services.database.replenishments_event.event_handlers_replenishments import replenishment_event_handler

    user = await create_new_user()
    new_replenishment = await create_replenishment(amount=105, user_id=user.user_id, status="processing")

    # Ломаем таблицу WalletTransaction, чтобы handler_new_replenishment упал
    async with get_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Table(WalletTransaction.__table__, MetaData()).drop(sync_conn)
        )

    await update_settings(channel_for_logging_id = 123456789)

    event = NewReplenishment(
        replenishment_id=new_replenishment.replenishment_id,
        user_id=new_replenishment.user_id,
        origin_amount=new_replenishment.origin_amount,
        amount=new_replenishment.amount
    )
    await replenishment_event_handler({"event": "replenishment.new_replenishment", "payload": event})

    # сообщение пользователю
    message_for_user = n_get_text(
        user.language,
        'replenishment',
        "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
        "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
        new_replenishment.amount
    ).format(sum=new_replenishment.amount)

    assert fake_bot.get_message(user.user_id, message_for_user)


@pytest.mark.asyncio
async def test_on_replenishment_completed(create_new_user):
    """
    Проверяет корректную работу on_replenishment_completed:
    - Пользователь получает сообщение об успешном пополнении
    - В лог уходит корректная запись
    """
    from src.services.database.replenishments_event.event_handlers_replenishments import on_replenishment_completed

    user = await create_new_user()
    amount = 150
    replenishment_id = 9999

    event = ReplenishmentCompleted(
        user_id=user.user_id,
        replenishment_id=replenishment_id,
        amount=amount,
        total_sum_replenishment=user.total_sum_replenishment + amount,
        error=False,
        error_str=None,
        language=user.language,
        username=user.username
    )
    await on_replenishment_completed(event)

    # сообщение пользователю
    message_success = n_get_text(
        user.language,
        "replenishment",
        "Balance successfully replenished by {sum} ruble.\nThank you for choosing us!",
        "Balance successfully replenished by {sum} rubles.\nThank you for choosing us!",
        amount
    ).format(sum=amount)
    assert fake_bot.get_message(user.user_id, message_success)


@pytest.mark.asyncio
async def test_on_replenishment_failed(create_new_user):
    """
    Проверяет корректную работу on_replenishment_failed:
    - Пользователь получает сообщение об ошибке
    - В лог уходит корректная запись
    """
    from src.services.database.replenishments_event.event_handlers_replenishments import on_replenishment_failed

    user = await create_new_user()
    replenishment_id = 8888
    error_text = "test_error"

    event = ReplenishmentFailed(
        user_id=user.user_id,
        replenishment_id=replenishment_id,
        error_str=error_text,
        language=user.language,
        username=user.username
    )

    await on_replenishment_failed(event)

    # сообщение пользователю
    message_for_user = get_text(
        user.language,
        "replenishment",
        "An error occurred while replenishing!\nReplenishment ID: {replenishment_id} "
        "\n\nWe apologize for the inconvenience. \nPlease contact support."
    ).format(replenishment_id=replenishment_id)
    assert fake_bot.get_message(user.user_id, message_for_user)
