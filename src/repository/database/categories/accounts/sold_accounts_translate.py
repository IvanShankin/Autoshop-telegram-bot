from __future__ import annotations

from typing import Optional, List, Any

from sqlalchemy import select, update, delete, func, distinct

from src.database.models.categories import (
    SoldAccountsTranslation,
)
from src.repository.database.base import DatabaseBase


class SoldAccountsTranslationRepository(DatabaseBase):

    async def get_by_sold_account_and_lang(
        self,
        sold_account_id: int,
        language: str,
    ) -> Optional[SoldAccountsTranslation]:
        result = await self.session_db.execute(
            select(SoldAccountsTranslation).where(
                (SoldAccountsTranslation.sold_account_id == sold_account_id)
                & (SoldAccountsTranslation.lang == language)
            )
        )
        return result.scalar_one_or_none()

    async def get_all_by_sold_account_id(
        self,
        sold_account_id: int,
    ) -> List[SoldAccountsTranslation]:
        result = await self.session_db.execute(
            select(SoldAccountsTranslation).where(
                SoldAccountsTranslation.sold_account_id == sold_account_id
            )
        )
        return list(result.scalars().all())

    async def get_languages_by_sold_account_id(self, sold_account_id: int) -> List[str]:
        result = await self.session_db.execute(
            select(distinct(SoldAccountsTranslation.lang)).where(
                SoldAccountsTranslation.sold_account_id == sold_account_id
            )
        )
        return list(result.scalars().all())

    async def exists(self, sold_account_id: int, language: str) -> bool:
        result = await self.session_db.execute(
            select(SoldAccountsTranslation.sold_account_id).where(
                (SoldAccountsTranslation.sold_account_id == sold_account_id)
                & (SoldAccountsTranslation.lang == language)
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_translate(self, **values) -> SoldAccountsTranslation:
        return await super().create(SoldAccountsTranslation, **values)

    async def update(
        self,
        sold_account_id: int,
        language: str,
        **values: Any,
    ) -> Optional[SoldAccountsTranslation]:
        if not values:
            return await self.get_by_sold_account_and_lang(sold_account_id, language)

        result = await self.session_db.execute(
            update(SoldAccountsTranslation)
            .where(
                (SoldAccountsTranslation.sold_account_id == sold_account_id)
                & (SoldAccountsTranslation.lang == language)
            )
            .values(**values)
            .returning(SoldAccountsTranslation)
        )
        return result.scalar_one_or_none()

    async def delete(self, sold_account_id: int, language: str) -> None:
        await self.session_db.execute(
            delete(SoldAccountsTranslation).where(
                (SoldAccountsTranslation.sold_account_id == sold_account_id)
                & (SoldAccountsTranslation.lang == language)
            )
        )

    async def delete_all_by_sold_account_id(self, sold_account_id: int) -> None:
        await self.session_db.execute(
            delete(SoldAccountsTranslation).where(
                SoldAccountsTranslation.sold_account_id == sold_account_id
            )
        )

    async def count_by_sold_account_id(self, sold_account_id: int) -> int:
        result = await self.session_db.execute(
            select(func.count()).select_from(SoldAccountsTranslation).where(
                SoldAccountsTranslation.sold_account_id == sold_account_id
            )
        )
        return int(result.scalar() or 0)