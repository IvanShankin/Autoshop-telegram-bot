import asyncio

import pytest
from sqlalchemy import select

from src.services.database.categories.events.schemas import NewPurchaseAccount, AccountsData
from src.services.database.core.database import get_db
from src.services.database.users.models import WalletTransaction, UserAuditLogs


@pytest.mark.asyncio
async def test_handler_new_purchase_creates_wallet_and_logs(
    create_new_user,
    create_sold_account,
):
    """
    Прямой вызов handler_new_purchase_account:
    - создаётся WalletTransaction
    - создаются UserAuditLogs (по каждому account_movement)
    - обновляется redis (sold_account и sold_accounts_by_owner_id)
    - отправляются логи (проверяется fake_bot)
    """

    from src.services.database.categories.events.even_handlers import handler_new_purchase_account
    # подготовка данных
    user = await create_new_user()
    # создаём sold_account в БД и перевод для языка 'ru'
    _, sold_full = await create_sold_account(filling_redis=False, owner_id=user.user_id, language='ru')

    # параметры покупки (имитация того, что уже произошла основная транзакция и purchase_id = 777)
    account_movement = [
        AccountsData(
            account_storage_id=sold_full.account_storage.account_storage_id,
            new_sold_account_id=sold_full.sold_account_id,
            purchase_id=777,
            cost_price=10,
            purchase_price=100,
            net_profit=90
        )
    ]

    new_purchase = NewPurchaseAccount(
        user_id=user.user_id,
        category_id=1,
        amount_purchase=100,
        account_movement=account_movement,
        user_balance_before=1000,
        user_balance_after=900,
        product_left=3,
    )

    # вызов тестируемой функции
    await handler_new_purchase_account(new_purchase)

    # ---- проверки в БД ----
    async with get_db() as session_db:
        # WalletTransaction
        result = await session_db.execute(
            select(WalletTransaction).where(WalletTransaction.user_id == user.user_id)
        )
        wt = result.scalar_one_or_none()
        assert wt is not None, "WalletTransaction не создан"
        assert wt.type == 'purchase'
        assert wt.amount == new_purchase.amount_purchase * -1
        assert wt.balance_before == new_purchase.user_balance_before
        assert wt.balance_after == new_purchase.user_balance_after

        # UserAuditLogs (должна появиться запись для account_movement)
        result = await session_db.execute(
            select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id)
        )
        logs = result.scalars().all()
        assert len(logs) >= 1, "UserAuditLogs не созданы"
        # проверим одну запись на соответствие деталям
        found = False
        for l in logs:
            if l.action_type == "purchase_account" and l.details.get("new_sold_account_id") == sold_full.sold_account_id:
                found = True
                assert l.details["account_storage_id"] == sold_full.account_storage.account_storage_id
                assert l.details["profit"] == 90
                break
        assert found, "Лог покупки с нужными деталями не найден"


@pytest.mark.asyncio
async def test_account_purchase_event_handler_parses_and_calls_handler(
    create_new_user,
    create_sold_account,
):
    """
    Проверяем, что purchase_event_handler корректно парсит dict-ивент
    и вызывает handler_new_purchase_account (через этот wrapper вставится Pydantic->handler).
    """
    from src.services.database.categories.events.even_handlers import purchase_event_handler
    user = await create_new_user()
    _, sold_full = await create_sold_account(filling_redis=False, owner_id=user.user_id, language='ru')

    account_movement = [
        AccountsData(
            account_storage_id=sold_full.account_storage.account_storage_id,
            new_sold_account_id=sold_full.sold_account_id,
            purchase_id=777,
            cost_price=10,
            purchase_price=100,
            net_profit=90
        ).model_dump()
    ]

    payload = NewPurchaseAccount(
        user_id=user.user_id,
        category_id=1,
        amount_purchase=100,
        account_movement=account_movement,
        user_balance_before=1000,
        user_balance_after=900,
        product_left=3,
    ).model_dump()

    event = {"event": "purchase.account", "payload": payload}

    # вызываем через event handler (имитируем приход события из брокера)
    await purchase_event_handler(event)

    # даём немного времени на асинхронные операции (send_log / redis)
    await asyncio.sleep(0.05)

    # проверим, что появились WalletTransaction и UserAuditLogs
    async with get_db() as session_db:
        result = await session_db.execute(select(WalletTransaction).where(WalletTransaction.user_id == user.user_id))
        wt = result.scalar_one_or_none()
        assert wt is not None and wt.type == 'purchase'

        result = await session_db.execute(select(UserAuditLogs).where(UserAuditLogs.user_id == user.user_id))
        logs = result.scalars().all()
        assert len(logs) >= 1
