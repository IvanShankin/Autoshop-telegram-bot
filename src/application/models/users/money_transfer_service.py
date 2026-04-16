from logging import Logger

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.read_models import LogLevel, EventSentLog
from src.config import Config
from src.exceptions import UserNotFound, NotEnoughMoney
from src.infrastructure.rabbit_mq.producer import publish_event
from src.models.create_models.users import CreateWalletTransactionDTO, CreateUserAuditLogDTO
from src.models.read_models import UsersDTO
from src.models.read_models.other import TransferMoneysDTO
from src.repository.database.users import TransferMoneysRepository
from src.repository.redis import UsersCacheRepository
from src.application.models.users.user_log_service import UserLogService
from src.application.models.users.user_service import UserService
from src.application.models.users.wallet_transaction import WalletTransactionService


class MoneyTransferService:

    def __init__(
        self,
        transfer_repo: TransferMoneysRepository,
        user_log_service: UserLogService,
        user_service: UserService,
        user_cache_repo: UsersCacheRepository,
        wallet_trans_service: WalletTransactionService,
        session_db: AsyncSession,
        conf: Config,
        logger: Logger,
    ):
        self.transfer_repo = transfer_repo
        self.user_log_service = user_log_service
        self.user_service = user_service
        self.user_cache_repo = user_cache_repo
        self.wallet_trans_service = wallet_trans_service
        self.session_db = session_db
        self.conf = conf
        self.logger = logger

    async def create_transfer(self, sender_id: int, recipient_id: int, amount: int):
        """
        :param sender_id: отправитель
        :param recipient_id: получатель
        :param amount: сумма
        :except UserNotFound: Если получатель не найден
        :except NotEnoughMoney: Если недостаточно денег
        """

        try:
            async with self.session_db.begin():

                sender = await self.user_service.get_user_for_update(sender_id)
                recipient = await self.user_service.get_user_for_update(recipient_id)

                if not recipient or not sender:
                    raise UserNotFound()

                if sender.balance < amount:
                    raise NotEnoughMoney("Not enough money to transfer", amount - sender.balance)

                sender.balance -= amount
                recipient.balance += amount

                transfer = await self.transfer_repo.create_transfer(
                    user_from_id=sender_id,
                    user_where_id=recipient_id,
                    amount=amount
                )
                await  self.wallet_trans_service.create_wallet_transaction(
                    user_id=sender_id,
                    data=CreateWalletTransactionDTO(
                        type="transfer",
                        amount=amount * -1,
                        balance_before=sender.balance - amount,
                        balance_after=sender.balance
                    )
                )
                await self.wallet_trans_service.create_wallet_transaction(
                    user_id=recipient_id,
                    data=CreateWalletTransactionDTO(
                        type='transfer',
                        amount=amount,
                        balance_before=recipient.balance - amount,  # т.к. ранее обновили баланс
                        balance_after=recipient.balance
                    )
                )
                # commit после выхода

            await self.user_cache_repo.set(UsersDTO.model_validate(sender), int(self.conf.redis_time_storage.user.total_seconds()))
            await self.user_cache_repo.set(UsersDTO.model_validate(recipient), int(self.conf.redis_time_storage.user.total_seconds()))

            await self.user_log_service.create_log(
                user_id=sender_id,
                data=CreateUserAuditLogDTO(
                    action_type="transfer",
                    message='Пользователь отправил средства',
                    details={
                        'transfer_money_id': transfer.transfer_money_id,
                        "recipient_id": recipient_id,
                        'amount': amount
                    }
                )
            )
            await self.user_log_service.create_log(
                user_id=recipient_id,
                data=CreateUserAuditLogDTO(
                    action_type="transfer",
                    message='Пользователь получил средства',
                    details={
                        'transfer_money_id': transfer.transfer_money_id,
                        "sender_id": sender_id,
                        'amount': amount
                    }
                )
            )
            await self.session_db.commit()
        except (UserNotFound, NotEnoughMoney) as e:
            raise e
        except Exception as e:
            self.logger.exception(f"#Ошибка_при_переводе_денег \n\nID пользователя: {sender_id} \nОшибка: {e}")
            event = EventSentLog(
                text=f"#Ошибка_при_переводе_денег \n\nID пользователя: {sender_id} \nОшибка: {e}",
            )
            await publish_event(event.model_dump(), "message.send_log")

    async def get_transfer_money(self, transfer_money_id: int) -> TransferMoneysDTO:
        return await self.transfer_repo.get_by_id(transfer_money_id)