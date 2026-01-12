from src.services.database.core.database import get_db
from src.services.database.categories.events.schemas import NewPurchaseAccount
from src.services.database.users.models import UserAuditLogs, WalletTransaction
from src.bot_actions.messages import send_log

async def account_purchase_event_handler(event):
    payload = event["payload"]

    if event["event"] == "account.purchase":
        obj = NewPurchaseAccount.model_validate(payload)
        await handler_new_purchase(obj)

async def handler_new_purchase(new_purchase: NewPurchaseAccount):
    """Отошлёт логи в канал, обновит SoldAccount в redis, добавить в БД запись о покупке"""
    logs = []
    for account_data in new_purchase.account_movement:
        text = (
            f"#Покупка_аккаунта \n\n"
            f"Аккаунт на продаже с id (StorageAccount) = {account_data.id_account_storage} продан!\n"
            f"Создана новая запись о проданном аккаунте (SoldAccount), id = {account_data.id_new_sold_account}\n"
            f"Создан лог о продаже аккаунта, id = {account_data.id_purchase_account}\n\n"
            f"Себестоимость: {account_data.cost_price}\n"
            f"Цена продажи: {account_data.purchase_price}\n"
            f"Прибыль: {account_data.net_profit}\n\n"
            f"ID категории: {new_purchase.category_id}\n"
            f"Осталось аккаунтов в категории: {new_purchase.accounts_left}\n"
        )
        await send_log(text)

        new_log = UserAuditLogs(
            user_id= new_purchase.user_id,
            action_type = "purchase_account",
            message="Пользователь купил аккаунт",
            details = {
                "id_account_storage": account_data.id_account_storage,
                "id_new_sold_account": account_data.id_new_sold_account,
                "id_purchase_account": account_data.id_purchase_account,
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
