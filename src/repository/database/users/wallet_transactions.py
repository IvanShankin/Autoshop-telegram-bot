from typing import Optional, Sequence

from sqlalchemy import func, select, update

from src.database.models.users import (
    WalletTransaction,
)
from src.repository.database.base import DatabaseBase


class WalletTransactionRepository(DatabaseBase):
    async def get_by_id(self, wallet_transaction_id: int) -> Optional[WalletTransaction]:
        result = await self.session_db.execute(
            select(WalletTransaction).where(
                WalletTransaction.wallet_transaction_id == wallet_transaction_id
            )
        )
        return result.scalar_one_or_none()

    async def get_page(
        self,
        user_id: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Sequence[WalletTransaction]:
        if page_size is None:
            page_size = self.conf.different.page_size

        stmt = (
            select(WalletTransaction)
            .where(WalletTransaction.user_id == user_id)
            .order_by(WalletTransaction.created_at.desc())
        )

        if page is not None:
            stmt = stmt.limit(page_size).offset((page - 1) * page_size)

        result = await self.session_db.execute(stmt)
        return result.scalars().all()

    async def count_by_user(self, user_id: int) -> int:
        result = await self.session_db.execute(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.user_id == user_id
            )
        )
        return int(result.scalar() or 0)

    async def create_transaction(self, **values) -> WalletTransaction:
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
