from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.create_models.users import CreateBannedAccountsDTO
from src.models.read_models import BannedAccountsDTO
from src.repository.database.users import BannedAccountsRepository
from src.repository.redis import BannedAccountsCacheRepository


class BannedAccountService:

    def __init__(
        self,
        banned_repo: BannedAccountsRepository,
        cache_repo: BannedAccountsCacheRepository,
        session_db: AsyncSession
    ):
        self.banned_repo = banned_repo
        self.cache_repo = cache_repo
        self.session_db = session_db

    async def create_ban(
        self,
        user_id: int,
        data: CreateBannedAccountsDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> BannedAccountsDTO:
        values = data.model_dump(exclude_unset=True)
        ban = await self.banned_repo.create_ban(user_id=user_id, **values)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_repo.set(user_id=ban.user_id, reason=ban.reason)

        return ban

    async def get_ban(self, user_id: int) -> Optional[str]:
        """ :return: Причина бана """
        return await self.cache_repo.get(user_id)

    async def delete_ban(
        self,
        user_id: int,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> None:
        await self.banned_repo.delete_by_user_id(user_id=user_id)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_repo.delete(user_id=user_id)