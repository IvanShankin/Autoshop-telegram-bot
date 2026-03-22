from __future__ import annotations

from typing import Optional, List, Any

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.database.models.categories import (
    AccountStorage,
    AccountServiceType,
)
from src.repository.database.base import DatabaseBase


class AccountStorageRepository(DatabaseBase):

    async def get_by_id(
        self,
        account_storage_id: int,
        *,
        with_relations: bool = False,
    ) -> Optional[AccountStorage]:
        stmt = select(AccountStorage).where(
            AccountStorage.account_storage_id == account_storage_id
        )
        if with_relations:
            stmt = stmt.options(
                selectinload(AccountStorage.product_account),
                selectinload(AccountStorage.sold_account),
                selectinload(AccountStorage.deleted_account),
            )

        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_storage(self, **values) -> AccountStorage:
        return await super().create(AccountStorage, **values)

    async def update(
        self,
        account_storage_id: int,
        **values: Any,
    ) -> Optional[AccountStorage]:
        if not values:
            return await self.get_by_id(account_storage_id)

        result = await self.session_db.execute(
            update(AccountStorage)
            .where(AccountStorage.account_storage_id == account_storage_id)
            .values(**values)
            .returning(AccountStorage)
        )
        return result.scalar_one_or_none()

    async def get_all_phone_numbers_by_service(
        self,
        type_account_service: AccountServiceType,
    ) -> List[str]:
        result = await self.session_db.execute(
            select(AccountStorage.phone_number).where(
                AccountStorage.type_account_service == type_account_service
            )
        )
        return list(result.scalars().all())

    async def get_all_tg_ids(self) -> List[int]:
        result = await self.session_db.execute(
            select(AccountStorage.tg_id)
            .where(AccountStorage.tg_id.is_not(None))
            .distinct()
        )
        return list(result.scalars().all())