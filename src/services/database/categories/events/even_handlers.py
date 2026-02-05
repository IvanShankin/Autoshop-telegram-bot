from src.bot_actions.messages.schemas import EventSentLog, LogLevel
from src.broker.producer import publish_event
from src.services.database.core.database import get_db
from src.services.database.categories.events.schemas import NewPurchaseAccount, NewPurchaseUniversal
from src.services.database.users.models import UserAuditLogs, WalletTransaction
from src.bot_actions.messages import send_log

async def purchase_event_handler(event):
    payload = event["payload"]

    if event["event"] == "purchase.account":
        obj = NewPurchaseAccount.model_validate(payload)
        await handler_new_purchase_account(obj)
    elif event["event"] == "purchase.universal":
        obj = NewPurchaseUniversal.model_validate(payload)
        await handler_new_purchase_universal(obj)

async def handler_new_purchase_account(new_purchase: NewPurchaseAccount):
    """Отошлёт логи в канал, обновит SoldAccount в redis, добавить в БД запись о покупке"""
    logs = []
    for account_data in new_purchase.account_movement:
        event = EventSentLog(
            text=(
                f"#Покупка_аккаунта \n\n"
                f"Аккаунт на продаже (StorageAccount), id = {account_data.account_storage_id} продан!\n"
                f"Создана новая запись о проданном аккаунте (SoldAccount), id = {account_data.new_sold_account_id}\n"
                f"Создан лог о продаже аккаунта, id = {account_data.purchase_id}\n\n"
                f"Себестоимость: {account_data.cost_price}\n"
                f"Цена продажи: {account_data.purchase_price}\n"
                f"Прибыль: {account_data.net_profit}\n\n"
                f"ID категории: {new_purchase.category_id}\n"
                f"Осталось аккаунтов в категории: {new_purchase.product_left}\n"
            ),
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")

        new_log = UserAuditLogs(
            user_id= new_purchase.user_id,
            action_type = "purchase_account",
            message="Пользователь купил аккаунт",
            details = {
                "account_storage_id": account_data.account_storage_id,
                "new_sold_account_id": account_data.new_sold_account_id,
                "id_purchase": account_data.purchase_id,
                "profit": account_data.net_profit,
            }
        )
        logs.append(new_log)


    new_wallet_transaction = WalletTransaction(
        user_id = new_purchase.user_id,
        type = 'purchase',
        amount = new_purchase.amount_purchase * -1,
        balance_before = new_purchase.user_balance_before,
        balance_after = new_purchase.user_balance_after
    )
    async with get_db() as session_db:
        session_db.add(new_wallet_transaction)
        for log in logs:
            session_db.add(log)

        await session_db.commit()


async def handler_new_purchase_universal(new_purchase: NewPurchaseUniversal):
    logs = []
    for product_data in new_purchase.product_movement:
        event = EventSentLog(
            text=(
                f"#Покупка \n\n"
                f"Продукт на продаже (UniversalStorage), id = {product_data.universal_storage_id} продан!\n"
                f"Создана новая запись о проданном товаре (SoldUniversal), id = {product_data.sold_universal_id}\n"
                f"Создан лог о продаже аккаунта, id = {product_data.purchase_id}\n\n"
                f"Себестоимость: {product_data.cost_price}\n"
                f"Цена продажи: {product_data.purchase_price}\n"
                f"Прибыль: {product_data.net_profit}\n\n"
                f"ID категории: {new_purchase.category_id}\n"
                f"Осталось продуктов в категории: {new_purchase.product_left}\n"
            ),
            log_lvl=LogLevel.INFO
        )
        await publish_event(event.model_dump(), "message.send_log")

        new_log = UserAuditLogs(
            user_id=new_purchase.user_id,
            action_type="purchase_universal_product",
            message="Пользователь купил универсальный товар",
            details={
                "id_universal_storage": product_data.universal_storage_id,
                "id_sold_universal": product_data.sold_universal_id,
                "id_purchase": product_data.purchase_id,
                "profit": product_data.net_profit,
            }
        )
        logs.append(new_log)

    new_wallet_transaction = WalletTransaction(
        user_id=new_purchase.user_id,
        type='purchase',
        amount=new_purchase.amount_purchase * -1,
        balance_before=new_purchase.user_balance_before,
        balance_after=new_purchase.user_balance_after
    )
    async with get_db() as session_db:
        session_db.add(new_wallet_transaction)
        for log in logs:
            session_db.add(log)

        await session_db.commit()