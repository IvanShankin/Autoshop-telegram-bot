from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.users import CreateWalletTransactionDTO
from src.models.read_models.other import WalletTransactionDTO
from src.repository.database.users import WalletTransactionRepository


class WalletTransactionService:

    def __init__(
        self,
        wallet_transaction: WalletTransactionRepository,
        session_db: AsyncSession,
    ):
        self.wallet_transaction = wallet_transaction
        self.session_db = session_db

    async def create_wallet_transaction(
        self,
        user_id: int,
        data: CreateWalletTransactionDTO,
        make_commit: Optional[bool] = False
    ) -> WalletTransactionDTO:
        values = data.model_dump()
        trans = await self.wallet_transaction.create_transaction(user_id=user_id, **values)

        if make_commit:
            await self.session_db.commit()

        return trans

    async def get_wallet_transaction(
        self,
        wallet_transaction_id: int
    ) -> WalletTransactionDTO:
        return await self.wallet_transaction.get_by_id(wallet_transaction_id=wallet_transaction_id)

    async def get_wallet_transaction_page(
        self,
        user_id: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> Sequence[WalletTransactionDTO]:
        return await self.wallet_transaction.get_page(user_id=user_id, page=page, page_size=page_size)

    async def get_count_wallet_transaction(self, user_id: int) -> int:
        return await self.wallet_transaction.count_by_user(user_id=user_id)

