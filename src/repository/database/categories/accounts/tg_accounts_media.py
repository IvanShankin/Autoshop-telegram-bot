from __future__ import annotations

from typing import Optional, Any

from sqlalchemy import select, update

from src.database.models.categories import (
    TgAccountMedia,
)
from src.repository.database.base import DatabaseBase


class TgAccountMediaRepository(DatabaseBase):

    async def get_by_account_storage_id(
        self,
        account_storage_id: int,
    ) -> Optional[TgAccountMedia]:
        result = await self.session_db.execute(
            select(TgAccountMedia).where(
                TgAccountMedia.account_storage_id == account_storage_id
            )
        )
        return result.scalar_one_or_none()

    async def create_media(self, **values) -> TgAccountMedia:
        return await super().create(TgAccountMedia, **values)

    async def update(
        self,
        tg_account_media_id: int,
        **values: Any,
    ) -> Optional[TgAccountMedia]:
        if not values:
            result = await self.session_db.execute(
                select(TgAccountMedia).where(
                    TgAccountMedia.tg_account_media_id == tg_account_media_id
                )
            )
            return result.scalar_one_or_none()

        result = await self.session_db.execute(
            update(TgAccountMedia)
            .where(TgAccountMedia.tg_account_media_id == tg_account_media_id)
            .values(**values)
            .returning(TgAccountMedia)
        )
        return result.scalar_one_or_none()
