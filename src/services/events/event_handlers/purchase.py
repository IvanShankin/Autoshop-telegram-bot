from sqlalchemy.ext.asyncio import AsyncSession

from src.bot_actions.messages.schemas import LogLevel
from src.models.create_models.users import CreateUserAuditLogDTO, CreateWalletTransactionDTO
from src.models.read_models import NewPurchaseAccount, NewPurchaseUniversal
from src.services.events.publish_event_handler import PublishEventHandler
from src.services.models.users import UserLogService, WalletTransactionService


class PurchaseEventHandler:

    def __init__(
        self,
        publish_event: PublishEventHandler,
        user_log_service: UserLogService,
        wallet_trans_service: WalletTransactionService,
        session_db: AsyncSession,
    ):
        self.publish_event = publish_event
        self.user_log_service = user_log_service
        self.wallet_trans_service = wallet_trans_service
        self.session_db = session_db

    async def purchase_event_handler(self, event):
        payload = event["payload"]

        if event["event"] == "purchase.account":
            obj = NewPurchaseAccount.model_validate(payload)
            await self._handler_new_purchase_account(obj)
        elif event["event"] == "purchase.universal":
            obj = NewPurchaseUniversal.model_validate(payload)
            await self._handler_new_purchase_universal(obj)

    async def _handler_new_purchase_account(self, new_purchase: NewPurchaseAccount):
        """Отошлёт логи в канал, обновит SoldAccount в redis, добавить в БД запись о покупке"""
        for account_data in new_purchase.account_movement:
            await self.publish_event.send_log(
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

            await self.user_log_service.create_log(
                user_id=new_purchase.user_id,
                data=CreateUserAuditLogDTO(
                    action_type="purchase_account",
                    message="Пользователь купил аккаунт",
                    details={
                        "account_storage_id": account_data.account_storage_id,
                        "new_sold_account_id": account_data.new_sold_account_id,
                        "id_purchase": account_data.purchase_id,
                        "profit": account_data.net_profit,
                    }
                )
            )

        await self.wallet_trans_service.create_wallet_transaction(
            user_id=new_purchase.user_id,
            data=CreateWalletTransactionDTO(
                type='purchase',
                amount=new_purchase.amount_purchase * -1,
                balance_before=new_purchase.user_balance_before,
                balance_after=new_purchase.user_balance_after
            )
        )

        await self.session_db.commit()


    async def _handler_new_purchase_universal(self, new_purchase: NewPurchaseUniversal):
        for product_data in new_purchase.product_movement:
            await self.publish_event.send_log(
                text=(
                    f"#Покупка \n\n"
                    f"Продукт на продаже (UniversalStorage), id = {product_data.universal_storage_id} продан!\n"
                    f"Создана новая запись о проданном товаре (SoldUniversal), id = {product_data.sold_universal_id}\n"
                    f"Создан лог о продаже товара, id = {product_data.purchase_id}\n\n"
                    f"Себестоимость: {product_data.cost_price}\n"
                    f"Цена продажи: {product_data.purchase_price}\n"
                    f"Прибыль: {product_data.net_profit}\n\n"
                    f"ID категории: {new_purchase.category_id}\n"
                    f"Осталось продуктов в категории: {new_purchase.product_left}\n"
                ),
                log_lvl=LogLevel.INFO
            )

            await self.user_log_service.create_log(
                user_id=new_purchase.user_id,
                data=CreateUserAuditLogDTO(
                    action_type="purchase_universal_product",
                    message="Пользователь купил универсальный товар",
                    details={
                        "id_universal_storage": product_data.universal_storage_id,
                        "id_sold_universal": product_data.sold_universal_id,
                        "id_purchase": product_data.purchase_id,
                        "profit": product_data.net_profit,
                    }
                )
            )

        await self.wallet_trans_service.create_wallet_transaction(
            user_id=new_purchase.user_id,
            data=CreateWalletTransactionDTO(
                type='purchase',
                amount=new_purchase.amount_purchase * -1,
                balance_before=new_purchase.user_balance_before,
                balance_after=new_purchase.user_balance_after
            )
        )

        await self.session_db.commit()
