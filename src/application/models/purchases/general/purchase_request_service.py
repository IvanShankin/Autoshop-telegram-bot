from src.exceptions.domain import UserNotFound
from src.models.read_models import PurchaseRequestsDTO, UsersDTO
from src.repository.database.categories import PurchaseRequestsRepository
from src.repository.database.users import BalanceHolderRepository, UsersRepository


class PurchaseRequestService:

    def __init__(
        self,
        purchase_request_repo: PurchaseRequestsRepository,
        balance_holder_repo: BalanceHolderRepository,
        users_repo: UsersRepository,
    ):
        self.purchase_request_repo = purchase_request_repo
        self.balance_holder_repo = balance_holder_repo
        self.users_repo = users_repo

    async def create_request(
        self,
        user_id: int,
        promo_code_id: int | None,
        quantity: int,
        total_amount: int,
    ) -> PurchaseRequestsDTO:
        return await self.purchase_request_repo.create_request(
            user_id=user_id,
            promo_code_id=promo_code_id,
            quantity=quantity,
            total_amount=total_amount,
        )

    async def hold_funds(
        self,
        user_id: int,
        purchase_request_id: int,
        amount: int,
    ) -> UsersDTO:
        """
        :exception UserNotFound: Если пользователь не найден.
        """
        await self.balance_holder_repo.create_holder(
            purchase_request_id=purchase_request_id,
            user_id=user_id,
            amount=amount,
        )
        user = await self.users_repo.update_balance_by_delta(user_id, -amount)
        if not user:
            raise UserNotFound()
        return user

    async def release_funds(self, user_id: int, amount: int) -> UsersDTO:
        """
        :exception UserNotFound: Если пользователь не найден.
        """
        user = await self.users_repo.update_balance_by_delta(user_id, amount)
        if not user:
            raise UserNotFound()
        return user

    async def mark_request_status(self, purchase_request_id: int, status: str) -> None:
        await self.purchase_request_repo.update_status(purchase_request_id, status)

    async def mark_balance_holder_status(self, purchase_request_id: int, status: str) -> None:
        await self.balance_holder_repo.update_status_by_request_id(purchase_request_id, status)
