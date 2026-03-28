from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.exceptions.domain import UniversalProductNotFound, UniversalStorageNotFound, UserNotFound
from src.models.create_models.universal import CreateSoldUniversalDTO
from src.models.read_models import SoldUniversalSmall, SoldUniversalFull, SoldUniversalDTO
from src.repository.database.categories.universal import (
    SoldUniversalRepository,
    UniversalStorageRepository,
)
from src.repository.database.users.users import UsersRepository
from src.repository.redis.product_universal import (
    SoldUniversalCacheRepository,
    SoldUniversalSingleCacheRepository,
)
from src.services.models.products.universal.universal_cache_filler_service import UniversalCacheFillerService


class UniversalSoldService:

    def __init__(
        self,
        sold_repo: SoldUniversalRepository,
        storage_repo: UniversalStorageRepository,
        user_repo: UsersRepository,
        sold_cache_repo: SoldUniversalCacheRepository,
        sold_single_cache_repo: SoldUniversalSingleCacheRepository,
        cache_filler: UniversalCacheFillerService,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.sold_repo = sold_repo
        self.storage_repo = storage_repo
        self.user_repo = user_repo
        self.sold_cache_repo = sold_cache_repo
        self.sold_single_cache_repo = sold_single_cache_repo
        self.cache_filler = cache_filler
        self.conf = conf
        self.session_db = session_db

    async def get_sold_universal_by_owner_id(
        self,
        owner_id: int,
        language: str,
    ) -> List[SoldUniversalSmall]:
        cached = await self.sold_cache_repo.get_by_owner(owner_id, language)
        if cached:
            return cached

        sold_items = await self.sold_repo.get_by_owner_with_relations(owner_id)
        result = [SoldUniversalSmall.from_orm_model(item, language) for item in sold_items]
        if result:
            ttl = int(self.conf.redis_time_storage.sold_universal_account_product_by_owner.total_seconds())
            await self.sold_cache_repo.set_by_owner(owner_id, language, result, ttl)
            await self.cache_filler.fill_sold_universal_by_owner_id(owner_id)
        return result

    async def get_sold_universal_by_page(
        self,
        user_id: int,
        page: int,
        language: str,
        page_size: Optional[int] = None,
    ) -> List[SoldUniversalSmall]:
        if page_size is None:
            page_size = self.conf.different.page_size

        sold_items = await self.sold_repo.get_page_by_owner(
            user_id,
            page=page,
            page_size=page_size,
            active_only=True,
        )
        await self.cache_filler.fill_sold_universal_by_owner_id(user_id)
        return [SoldUniversalSmall.from_orm_model(item, language) for item in sold_items]

    async def get_sold_universal_by_universal_id(
        self,
        sold_universal_id: int,
        language: str,
    ) -> SoldUniversalFull | None:
        cached = await self.sold_single_cache_repo.get(sold_universal_id, language)
        if cached:
            return cached

        sold_item = await self.sold_repo.get_by_id_with_relations(sold_universal_id)
        if not sold_item:
            return None

        await self.cache_filler.fill_sold_universal_by_universal_id(sold_universal_id)
        return SoldUniversalFull.from_orm_model(sold_item, language)

    async def get_count_sold_universal(self, user_id: int) -> int:
        return await self.sold_repo.count_by_owner(user_id)

    async def create_sold_universal(
        self,
        data: CreateSoldUniversalDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> SoldUniversalDTO:
        """
        :exception UserNotFound: Пользователь не найден.
        :exception UniversalStorageNotFound: Хранилище не найдено.
        """
        if not await self.user_repo.get_by_id(data.owner_id):
            raise UserNotFound()

        if not await self.storage_repo.get_by_id(data.universal_storage_id):
            raise UniversalStorageNotFound()

        sold = await self.sold_repo.create_sold(**data.model_dump(exclude_unset=True))

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_filler.fill_sold_universal_by_owner_id(sold.owner_id)
            await self.cache_filler.fill_sold_universal_by_universal_id(sold.sold_universal_id)

        return sold

    async def delete_sold_universal(
        self,
        sold_universal_id: int,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> None:
        """
        :exception UniversalProductNotFound: Проданный товар не найден.
        """
        sold = await self.sold_repo.get_by_id(sold_universal_id)
        if not sold:
            raise UniversalProductNotFound(
                f"Продукт с id = {sold_universal_id} не найден"
            )

        await self.sold_repo.delete(sold_universal_id)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_filler.fill_sold_universal_by_owner_id(sold.owner_id)
            await self.cache_filler.fill_sold_universal_by_universal_id(sold_universal_id)
