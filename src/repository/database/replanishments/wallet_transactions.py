from typing import Optional, Sequence

from sqlalchemy import select, update

from src.database.models.users import WalletTransaction
from src.repository.database.base import DatabaseBase


class WalletTransactionRepository(DatabaseBase):

    async def get_by_id(self, wallet_transaction_id: int) -> Optional[WalletTransaction]:
        stmt = select(WalletTransaction).where(WalletTransaction.wallet_transaction_id == wallet_transaction_id)
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int) -> Sequence[WalletTransaction]:
        stmt = select(WalletTransaction).where(WalletTransaction.user_id == user_id)
        result = await self.session_db.execute(stmt)
        return result.scalars().all()

    async def create_wallet_trans(self, **values) -> WalletTransaction:
        return await super().create(WalletTransaction, **values)

    async def update(self, wallet_transaction_id: int, **values) -> Optional[WalletTransaction]:
        if not values:
            return await self.get_by_id(wallet_transaction_id)

        stmt = (
            update(WalletTransaction)
            .where(WalletTransaction.wallet_transaction_id == wallet_transaction_id)
            .values(**values)
            .returning(WalletTransaction)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()
