from __future__ import annotations

from typing import Optional, List

from sqlalchemy import select, delete, func, distinct
from sqlalchemy.orm import selectinload

from src.database.models.categories import (
    SoldAccounts,
    AccountStorage,
    AccountServiceType,
)
from src.read_models import SoldAccountsDTO
from src.repository.database.base import DatabaseBase


class SoldAccountsRepository(DatabaseBase):

    async def get_by_id(
        self,
        sold_account_id: int,
        *,
        with_relations: bool = False,
    ) -> Optional[SoldAccountsDTO]:
        stmt = select(SoldAccounts).where(
            SoldAccounts.sold_account_id == sold_account_id
        )
        if with_relations:
            stmt = stmt.options(
                selectinload(SoldAccounts.translations),
                selectinload(SoldAccounts.account_storage),
            )

        result = await self.session_db.execute(stmt)
        sold_account = result.scalar_one_or_none()
        return SoldAccountsDTO.model_validate(sold_account) if sold_account else None

    async def get_by_owner_id(
        self,
        owner_id: int,
        *,
        active_only: bool = True,
        with_relations: bool = False,
        order_desc: bool = True,
    ) -> List[SoldAccountsDTO]:
        stmt = select(SoldAccounts).where(SoldAccounts.owner_id == owner_id)

        if active_only:
            stmt = stmt.where(SoldAccounts.account_storage.has(is_active=True))

        if with_relations:
            stmt = stmt.options(
                selectinload(SoldAccounts.translations),
                selectinload(SoldAccounts.account_storage),
            )

        if order_desc:
            stmt = stmt.order_by(SoldAccounts.sold_at.desc())

        result = await self.session_db.execute(stmt)
        sold_accounts = list(result.scalars().all())
        return [SoldAccountsDTO.model_validate(item) for item in sold_accounts]

    async def count_by_owner_id(
        self,
        owner_id: int,
        *,
        type_account_service: AccountServiceType,
        active_only: bool = True,
    ) -> int:
        stmt = (
            select(func.count(SoldAccounts.sold_account_id))
            .join(SoldAccounts.account_storage)
            .where(
                (SoldAccounts.owner_id == owner_id)
                & (AccountStorage.type_account_service == type_account_service)
            )
        )
        if active_only:
            stmt = stmt.where(SoldAccounts.account_storage.has(is_active=True))

        result = await self.session_db.execute(stmt)
        return int(result.scalar() or 0)

    async def get_distinct_account_service_types_by_owner(
        self,
        owner_id: int,
        *,
        active_only: bool = True,
    ) -> List[AccountServiceType]:
        stmt = (
            select(distinct(AccountStorage.type_account_service))
            .select_from(SoldAccounts)
            .join(SoldAccounts.account_storage)
            .where(SoldAccounts.owner_id == owner_id)
        )
        if active_only:
            stmt = stmt.where(SoldAccounts.account_storage.has(is_active=True))

        result = await self.session_db.execute(stmt)
        return list(result.scalars().all())

    async def create_sold(self, **values) -> SoldAccountsDTO:
        created = await super().create(SoldAccounts, **values)
        return SoldAccountsDTO.model_validate(created)

    async def delete_by_id(self, sold_account_id: int) -> None:
        await self.session_db.execute(
            delete(SoldAccounts).where(SoldAccounts.sold_account_id == sold_account_id)
        )

    async def exists_by_id(self, sold_account_id: int) -> bool:
        result = await self.session_db.execute(
            select(SoldAccounts.sold_account_id).where(
                SoldAccounts.sold_account_id == sold_account_id
            )
        )
        return result.scalar_one_or_none() is not None
