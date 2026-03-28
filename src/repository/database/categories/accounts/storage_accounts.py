from __future__ import annotations

from typing import Optional, List, Any

from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from src.database.models.categories import (
    AccountStorage,
    AccountServiceType,
    StorageStatus,
)
from src.models.read_models import AccountStorageDTO
from src.repository.database.base import DatabaseBase


class AccountStorageRepository(DatabaseBase):

    async def get_by_id(
        self,
        account_storage_id: int,
        *,
        with_relations: bool = False,
    ) -> Optional[AccountStorageDTO]:
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
        storage = result.scalar_one_or_none()
        return AccountStorageDTO.model_validate(storage) if storage else None

    async def create_storage(self, **values) -> AccountStorageDTO:
        created = await super().create(AccountStorage, **values)
        return AccountStorageDTO.model_validate(created)

    async def update(
        self,
        account_storage_id: int,
        **values: Any,
    ) -> Optional[AccountStorageDTO]:
        if not values:
            return await self.get_by_id(account_storage_id)

        result = await self.session_db.execute(
            update(AccountStorage)
            .where(AccountStorage.account_storage_id == account_storage_id)
            .values(**values)
            .returning(AccountStorage)
        )
        storage = result.scalar_one_or_none()
        return AccountStorageDTO.model_validate(storage) if storage else None

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

    async def delete_by_ids(self, account_storage_ids: List[int]) -> List[AccountStorageDTO]:
        if not account_storage_ids:
            return []

        result = await self.session_db.execute(
            delete(AccountStorage)
            .where(AccountStorage.account_storage_id.in_(account_storage_ids))
            .returning(AccountStorage)
        )
        deleted = list(result.scalars().all())
        return [AccountStorageDTO.model_validate(item) for item in deleted]

    async def update_status_by_ids(
        self,
        account_storage_ids: List[int],
        *,
        status: StorageStatus,
        is_active: bool | None = None,
        is_valid: bool | None = None,
    ) -> None:
        if not account_storage_ids:
            return

        values: dict[str, Any] = {"status": status}
        if is_active is not None:
            values["is_active"] = is_active
        if is_valid is not None:
            values["is_valid"] = is_valid

        await self.session_db.execute(
            update(AccountStorage)
            .where(AccountStorage.account_storage_id.in_(account_storage_ids))
            .values(**values)
        )
