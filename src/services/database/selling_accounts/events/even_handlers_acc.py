from src.services.redis.filling_redis import filling_sold_accounts_by_owner_id, filling_sold_account_by_account_id
from src.services.database.core.database import get_db
from src.services.database.selling_accounts.events.schemas import NewPurchaseAccount
from src.services.database.users.models import UserAuditLogs, WalletTransaction
from src.bot_actions.actions import send_log

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
            f"Аккаунт на продаже с id = {account_data.id_old_product_account} продан!\n"
            f"Создана новая запись о проданном аккаунте, id = {account_data.id_new_sold_account}\n"
            f"Создан лог о продаже аккаунта, id = {account_data.id_purchase_account}\n\n"
            f"Себестоимость: {account_data.cost_price}\n"
            f"Цена продажи: {account_data.purchase_price}\n"
            f"Прибыль: {account_data.net_profit}\n"
        )
        await send_log(text)

        new_log = UserAuditLogs(
            user_id= new_purchase.user_id,
            action_type = "purchase_account",
            details = {
                "id_old_product_account": account_data.id_old_product_account,
                "id_new_sold_account": account_data.id_new_sold_account,
                "id_purchase_account": account_data.id_purchase_account,
                "profit": account_data.net_profit,
            }
        )
        logs.append(new_log)

        # обновление redis по каждому проданный аккаунт
        await filling_sold_account_by_account_id(account_data.id_new_sold_account)

    # обновление redis у всего пользователя
    await filling_sold_accounts_by_owner_id(new_purchase.user_id)


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


