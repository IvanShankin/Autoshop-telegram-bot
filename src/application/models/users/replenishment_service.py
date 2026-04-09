from typing import Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.users import CreateReplenishmentDTO, CreateUserAuditLogDTO, CreateWalletTransactionDTO
from src.models.read_models import NewReplenishment, ReplenishmentCompleted, ReplenishmentFailed
from src.models.read_models.other import ReplenishmentsDTO
from src.models.update_models.users import UpdateReplenishment
from src.repository.database.replanishments import ReplenishmentsRepository
from src.models.read_models.other import UsersDTO
from src.application.models.users.user_log_service import UserLogService
from src.application.models.users.user_service import UserService
from src.application.models.users.wallet_transaction import WalletTransactionService


class ReplenishmentsService:

    def __init__(
        self,
        replenishment_repo: ReplenishmentsRepository,
        user_service: UserService,
        user_log_service: UserLogService,
        wallet_transaction_service: WalletTransactionService,
        session_db: AsyncSession,
    ):
        self.replenishment_repo = replenishment_repo
        self.user_service = user_service
        self.user_log_service = user_log_service
        self.wallet_transaction_service = wallet_transaction_service
        self.session_db = session_db

    async def create_replenishment(
        self,
        user_id: int,
        type_payment_id: int,
        data: CreateReplenishmentDTO,
        make_commit: Optional[bool] = False
    ) -> ReplenishmentsDTO:
        """Создает Replenishments в БД. Статус выставляется автоматически 'pending' """
        values = data.model_dump()
        rep = await self.replenishment_repo.create_replenishment(
            user_id=user_id, type_payment_id=type_payment_id, **values
        )

        if make_commit:
            await self.session_db.commit()

        return rep

    async def get_replenishment(
        self,
        replenishment_id: int,
    ) -> ReplenishmentsDTO:
        return await self.replenishment_repo.get_by_id(replenishment_id)

    async def update_replenishment(
        self,
        replenishment_id: int,
        data: UpdateReplenishment,
        make_commit: Optional[bool] = False
    ) -> Optional[ReplenishmentsDTO]:
        values = data.model_dump(exclude_unset=True)
        rep = await self.replenishment_repo.update(replenishment_id, **values)

        if make_commit:
            await self.session_db.commit()

        return rep

    async def process_new_replenishment(
        self,
        data: NewReplenishment,
    ) -> Optional[Union[ReplenishmentCompleted, ReplenishmentFailed]]:
        """
        Обрабатывает событие пополнения:
        - проверяет статус replenishment (должен быть processing)
        - начисляет баланс пользователю и обновляет total_sum_replenishment
        - создает транзакцию и лог
        - меняет статус пополнения на completed или error
        """
        money_credited = False
        error = True
        error_str: str | None = None
        language = "ru"
        username: str | None = None
        total_sum_replenishment: int | None = None
        user = None

        try:
            async with self.session_db.begin():
                replenishment = await self.replenishment_repo.get_by_id_for_update(
                    data.replenishment_id
                )
                if not replenishment or replenishment.status != "processing":
                    return None

                user = await self.user_service.get_user_for_update(data.user_id)
                if not user:
                    return None

                user.balance += data.amount
                user.total_sum_replenishment = (user.total_sum_replenishment or 0) + data.amount

                language = user.language
                username = user.username
                total_sum_replenishment = user.total_sum_replenishment

                replenishment.status = "completed"

                transaction = await self.wallet_transaction_service.create_wallet_transaction(
                    user_id=data.user_id,
                    data=CreateWalletTransactionDTO(
                        type="replenish",
                        amount=data.amount,
                        balance_before=user.balance - data.amount,
                        balance_after=user.balance,
                    ),
                )

                await self.user_log_service.create_log(
                    user_id=data.user_id,
                    data=CreateUserAuditLogDTO(
                        action_type="replenish",
                        message="Пользователь пополнил баланс",
                        details={
                            "replenishment_id": data.replenishment_id,
                            "wallet_transaction_id": transaction.wallet_transaction_id,
                            "amount": data.amount,
                            "new_balance": user.balance,
                        },
                    ),
                )

            money_credited = True
            error = False

        except Exception as e:
            error_str = str(e)
            await self._update_replenishment_status_on_error(
                replenishment_id=data.replenishment_id,
                status="completed" if money_credited else "error",
            )

        if money_credited and user is not None:
            await self.user_service.cache_user_repo.set(
                user=UsersDTO.model_validate(user),
                ttl=int(self.user_service.conf.redis_time_storage.user.total_seconds()),
            )

            return ReplenishmentCompleted(
                user_id=data.user_id,
                replenishment_id=data.replenishment_id,
                amount=data.amount,
                total_sum_replenishment=total_sum_replenishment,
                error=error,
                error_str=error_str,
                language=language,
                username=username,
            )

        return ReplenishmentFailed(
            user_id=data.user_id,
            replenishment_id=data.replenishment_id,
            error_str=error_str,
            language=language,
            username=username,
        )

    async def _update_replenishment_status_on_error(
        self,
        replenishment_id: int,
        status: str,
    ) -> None:
        try:
            async with self.session_db.begin():
                await self.replenishment_repo.update(
                    replenishment_id=replenishment_id,
                    status=status,
                )
                await self.session_db.commit()
        except Exception:
            return

