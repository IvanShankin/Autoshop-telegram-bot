from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.accounts import CreateTgAccountMediaDTO
from src.models.read_models import TgAccountMediaDTO
from src.models.update_models.accounts import UpdateTgAccountMediaDTO
from src.repository.database.categories.accounts import TgAccountMediaRepository


class AccountTgMediaService:

    def __init__(
        self,
        tg_media_repo: TgAccountMediaRepository,
        session_db: AsyncSession,
    ):
        self.tg_media_repo = tg_media_repo
        self.session_db = session_db

    async def get_tg_account_media(self, account_storage_id: int) -> TgAccountMediaDTO | None:
        return await self.tg_media_repo.get_by_account_storage_id(account_storage_id)

    async def create_tg_account_media(
        self,
        data: CreateTgAccountMediaDTO,
        make_commit: Optional[bool] = True,
    ) -> TgAccountMediaDTO:
        media = await self.tg_media_repo.create_media(**data.model_dump(exclude_unset=True))
        if make_commit:
            await self.session_db.commit()
        return media

    async def update_tg_account_media(
        self,
        tg_account_media_id: int,
        data: UpdateTgAccountMediaDTO,
        make_commit: Optional[bool] = True,
    ) -> TgAccountMediaDTO | None:
        values = data.model_dump(exclude_unset=True)
        media = await self.tg_media_repo.update(tg_account_media_id, **values)
        if make_commit:
            await self.session_db.commit()
        return media
