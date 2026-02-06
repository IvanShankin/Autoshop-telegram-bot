import pytest
from sqlalchemy import MetaData, Table
from sqlalchemy import select

from src.services.database.core.database import get_db
from src.services.database.discounts.models import Vouchers
from src.services.database.system.actions import update_settings
from src.services.database.users.models import Users, WalletTransaction, UserAuditLogs
from src.services.redis.core_redis import get_redis
from src.utils.i18n import get_text
from tests.helpers.monkeypatch_data import fake_bot

async def _create_voucher_activation_event(
    user: Users,
    voucher: Vouchers,
    balance_before: int,
    balance_after: int
):
    """Создает событие активации ваучера"""
    from src.services.database.discounts.events import NewActivationVoucher

    return NewActivationVoucher(
        voucher_id=voucher.voucher_id,
        user_id=user.user_id,
        language=user.language,
        amount=voucher.amount,
        balance_before=balance_before,
        balance_after=balance_after
    )

@pytest.mark.asyncio
async def test_successful_voucher_activation(
    create_new_user,
    create_voucher,
):
    """Тест успешной активации ваучера"""
    from src.services.database.users.actions import get_user
    from src.services.database.discounts.events import handler_new_activated_voucher

    user = await create_new_user()
    voucher = await create_voucher(is_created_admin=False)
    initial_balance = user.balance
    expected_balance = initial_balance + voucher.amount

    # Создаем событие активации
    event = await _create_voucher_activation_event(
        user, voucher, initial_balance, expected_balance
    )

    await handler_new_activated_voucher(event)

    async with get_db() as session_db:
        # Проверяем обновление ваучера
        voucher_result = await session_db.execute(
            select(Vouchers).where(Vouchers.voucher_id == voucher.voucher_id)
        )
        updated_voucher = voucher_result.scalar_one()
        assert updated_voucher.activated_counter == voucher.activated_counter + 1

        # Проверяем транзакцию кошелька
        transaction_result = await session_db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user.user_id)
        )
        wallet_transaction = transaction_result.scalar_one()
        assert wallet_transaction.type == 'voucher'
        assert wallet_transaction.amount == voucher.amount
        assert wallet_transaction.balance_before == initial_balance
        assert wallet_transaction.balance_after == expected_balance

        # Проверяем лог аудита
        log_result = await session_db.execute(
            select(UserAuditLogs)
            .where(UserAuditLogs.user_id == user.user_id)
        )
        assert log_result.scalar_one()

    owner = await get_user(voucher.creator_id)
    message_for_user = get_text(
        owner.language,
        "discount",
        "log_voucher_activated"
    ).format(
        code=updated_voucher.activation_code,
        number_activations=updated_voucher.number_of_activations - updated_voucher.activated_counter
    )

    assert fake_bot.get_message(owner.user_id, message_for_user)


@pytest.mark.asyncio
async def test_voucher_activation_with_activation_limit(
    create_new_user,
    create_voucher,
    clean_rabbit,
):
    """Тест активации ваучера с достижением лимита активаций"""
    from src.services.database.discounts.events import handler_new_activated_voucher

    user = await create_new_user()
    voucher = await create_voucher(number_of_activations=1)

    activation_amount = voucher.amount
    initial_balance = user.balance
    expected_balance = initial_balance + activation_amount

    event = await _create_voucher_activation_event(user, voucher, initial_balance, expected_balance)

    await handler_new_activated_voucher(event)

    async with get_db() as session_db:
        # Проверяем, что ваучер стал невалидным
        voucher_result = await session_db.execute(
            select(Vouchers).where(Vouchers.voucher_id == voucher.voucher_id)
        )
        updated_voucher = voucher_result.scalar_one()
        assert not updated_voucher.is_valid
        assert updated_voucher.activated_counter == 1

        # Проверяем удаление ваучера из Redis
        async with get_redis() as session_redis:
            redis_result = await session_redis.get(f"voucher:{voucher.activation_code}")
            assert not redis_result

    # Проверяем отправку сообщения об истечении ваучера
    expected_user_message = get_text(
        'ru',
        "discount",
        "voucher_reached_activation_limit"
    ).format(id=voucher.voucher_id, code=voucher.activation_code)

    assert fake_bot.get_message(voucher.creator_id, expected_user_message)


@pytest.mark.asyncio
async def test_voucher_activation_failure(
    create_new_user,
    create_voucher,
    get_engine,
):
    """Тест обработки ошибки при активации ваучера"""
    from src.services.database.discounts.events import handler_new_activated_voucher

    user = await create_new_user()
    voucher = await create_voucher()

    # Ломаем таблицу VoucherActivations чтобы вызвать ошибку
    async with get_engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Table(WalletTransaction.__table__, MetaData()).drop(sync_conn)
        )

    activation_amount = voucher.amount
    initial_balance = user.balance
    expected_balance = initial_balance + activation_amount

    event = await _create_voucher_activation_event(
        user, voucher, initial_balance, expected_balance
    )

    # Настраиваем канал для логов
    await update_settings(channel_for_logging_id = 123456789)

    await handler_new_activated_voucher(event)


@pytest.mark.asyncio
@pytest.mark.parametrize('is_created_admin', [True, False])
async def test_send_set_not_valid_voucher(
    is_created_admin,
    create_new_user,
    create_voucher,
):
    """Тест отправки сообщений при истечении ваучера"""
    from src.services.database.discounts.utils.set_not_valid import send_set_not_valid_voucher

    user = await create_new_user()
    voucher = await create_voucher(is_created_admin=is_created_admin)

    # Настраиваем канал для логов если ваучер создан админом
    if is_created_admin:
        await update_settings(channel_for_logging_id=123)

    await send_set_not_valid_voucher(user.user_id, voucher, True, user.language)

    if not is_created_admin:
        # Проверяем сообщение пользователю
        expected_user_message = get_text(
            user.language,
            "discount",
            "voucher_reached_activation_limit"
        ).format(id=voucher.voucher_id, code=voucher.activation_code)
        assert fake_bot.get_message(user.user_id, expected_user_message)


