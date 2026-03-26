from __future__ import annotations

from typing import Optional, Any

from sqlalchemy import select, update

from src.database.models.categories import (
    TgAccountMedia,
)
from src.models.read_models import TgAccountMediaDTO
from src.repository.database.base import DatabaseBase


class TgAccountMediaRepository(DatabaseBase):

    async def get_by_account_storage_id(
        self,
        account_storage_id: int,
    ) -> Optional[TgAccountMediaDTO]:
        result = await self.session_db.execute(
            select(TgAccountMedia).where(
                TgAccountMedia.account_storage_id == account_storage_id
            )
        )
        media = result.scalar_one_or_none()
        return TgAccountMediaDTO.model_validate(media) if media else None

    async def create_media(self, **values) -> TgAccountMediaDTO:
        created = await super().create(TgAccountMedia, **values)
        return TgAccountMediaDTO.model_validate(created)

    async def update(
        self,
        tg_account_media_id: int,
        **values: Any,
    ) -> Optional[TgAccountMediaDTO]:
        if not values:
            result = await self.session_db.execute(
                select(TgAccountMedia).where(
                    TgAccountMedia.tg_account_media_id == tg_account_media_id
                )
            )
            media = result.scalar_one_or_none()
            return TgAccountMediaDTO.model_validate(media) if media else None

        result = await self.session_db.execute(
            update(TgAccountMedia)
            .where(TgAccountMedia.tg_account_media_id == tg_account_media_id)
            .values(**values)
            .returning(TgAccountMedia)
        )
        media = result.scalar_one_or_none()
        return TgAccountMediaDTO.model_validate(media) if media else None
