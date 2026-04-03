from typing import Optional, Sequence

from sqlalchemy import func, select, update

from src.database.models.users import (
    WalletTransaction,
)
from src.models.read_models.other import WalletTransactionDTO
from src.repository.database.base import DatabaseBase


class WalletTransactionRepository(DatabaseBase):

    async def get_by_id(self, wallet_transaction_id: int) -> Optional[WalletTransactionDTO]:
        result = await self.session_db.execute(
            select(WalletTransaction).where(
                WalletTransaction.wallet_transaction_id == wallet_transaction_id
            )
        )
        wallet_tx = result.scalar_one_or_none()
        return WalletTransactionDTO.model_validate(wallet_tx) if wallet_tx else None

    async def get_by_user(self, user_id: int) -> Sequence[WalletTransactionDTO]:
        stmt = select(WalletTransaction).where(WalletTransaction.user_id == user_id)
        result = await self.session_db.execute(stmt)
        transactions = list(result.scalars().all())
        return [WalletTransactionDTO.model_validate(tx) for tx in transactions]

    async def get_page(
        self,
        user_id: int,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Sequence[WalletTransactionDTO]:
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
        transactions = list(result.scalars().all())
        return [WalletTransactionDTO.model_validate(tx) for tx in transactions]

    async def count_by_user(self, user_id: int) -> int:
        result = await self.session_db.execute(
            select(func.count()).select_from(WalletTransaction).where(
                WalletTransaction.user_id == user_id
            )
        )
        return int(result.scalar() or 0)

    async def create_transaction(self, **values) -> WalletTransactionDTO:
        created = await super().create(WalletTransaction, **values)
        return WalletTransactionDTO.model_validate(created)

    async def update(self, wallet_transaction_id: int, **values) -> Optional[WalletTransactionDTO]:
        if not values:
            return await self.get_by_id(wallet_transaction_id)

        stmt = (
            update(WalletTransaction)
            .where(WalletTransaction.wallet_transaction_id == wallet_transaction_id)
            .values(**values)
            .returning(WalletTransaction)
        )
        result = await self.session_db.execute(stmt)
        updated = result.scalar_one_or_none()
        return WalletTransactionDTO.model_validate(updated) if updated else None
