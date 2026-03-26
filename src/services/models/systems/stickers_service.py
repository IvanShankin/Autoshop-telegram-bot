from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.exceptions.domain import MessageEventNotFound
from src.models.create_models.system import CreateStickerDTO
from src.models.read_models.other import StickersDTO
from src.models.update_models.system import UpdateStickerDTO
from src.repository.database.systems import StickersRepository
from src.repository.redis import StickersCacheRepository


class StickersService:

    def __init__(
        self,
        sticker_repo: StickersRepository,
        cache_repo: StickersCacheRepository,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.sticker_repo = sticker_repo
        self.cache_repo = cache_repo
        self.conf = conf
        self.session_db = session_db

    async def create_sticker(
        self,
        key: str,
        data: CreateStickerDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> StickersDTO:
        if key not in self.conf.message_event.all_keys:
            raise MessageEventNotFound()

        values = data.model_dump()
        sticker = await self.sticker_repo.create_sticker(key=key, **values)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_repo.set(sticker)

        return sticker

    async def get_sticker(self, key: str) -> Optional[StickersDTO]:
        sticker = await self.cache_repo.get(key)
        if sticker:
            return sticker

        return await self.sticker_repo.get_by_key(key)

    async def update_sticker(
        self,
        key: str,
        data: UpdateStickerDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> Optional[StickersDTO]:
        values = data.model_dump(exclude_unset=True)
        sticker = await self.sticker_repo.update(key=key, **values)

        if make_commit:
            await self.session_db.commit()

        if sticker and filling_redis:
            await self.cache_repo.set(sticker)

        return sticker

    async def delete_sticker(
        self,
        key: str,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> Optional[StickersDTO]:
        deleted = await self.sticker_repo.delete(key=key)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_repo.delete(key)

        return deleted
