from typing import Iterable

from src.config import Config
from src.database.models.categories import SoldUniversal
from src.models.read_models import (
    ProductUniversalSmall,
    SoldUniversalSmall,
    SoldUniversalFull,
)
from src.repository.database.categories.universal import (
    ProductUniversalRepository,
    SoldUniversalRepository,
)
from src.repository.redis.product_universal import (
    ProductUniversalCacheRepository,
    ProductUniversalSingleCacheRepository,
    SoldUniversalCacheRepository,
    SoldUniversalSingleCacheRepository,
)


class UniversalCacheFillerService:

    def __init__(
        self,
        product_repo: ProductUniversalRepository,
        sold_repo: SoldUniversalRepository,
        product_cache_repo: ProductUniversalCacheRepository,
        product_single_cache_repo: ProductUniversalSingleCacheRepository,
        sold_cache_repo: SoldUniversalCacheRepository,
        sold_single_cache_repo: SoldUniversalSingleCacheRepository,
        conf: Config,
    ):
        self.product_repo = product_repo
        self.sold_repo = sold_repo
        self.product_cache_repo = product_cache_repo
        self.product_single_cache_repo = product_single_cache_repo
        self.sold_cache_repo = sold_cache_repo
        self.sold_single_cache_repo = sold_single_cache_repo
        self.conf = conf

    async def fill_product_universal_by_category_id(self, category_id: int) -> None:
        products = await self.product_repo.get_by_category_for_sale(category_id)
        if not products:
            await self.product_cache_repo.delete_by_category(category_id)
            return

        items = [ProductUniversalSmall(**p.model_dump()) for p in products]
        await self.product_cache_repo.set_by_category(category_id, items)

    async def fill_product_universal_by_product_id(self, product_universal_id: int) -> None:
        product = await self.product_repo.get_full_by_id(
            product_universal_id,
            language=self.conf.app.default_lang,
        )
        if not product:
            await self.product_single_cache_repo.delete_by_product_id(product_universal_id)
            return

        await self.product_single_cache_repo.set(product)

    async def fill_sold_universal_by_owner_id(self, owner_id: int) -> None:
        sold_items = await self.sold_repo.get_by_owner_with_relations(owner_id)
        if not sold_items:
            await self.sold_cache_repo.delete_by_owner(owner_id)
            return

        languages = self._extract_languages(sold_items)
        if not languages:
            await self.sold_cache_repo.delete_by_owner(owner_id)
            return

        ttl = int(self.conf.redis_time_storage.sold_universal_account_product_by_owner.total_seconds())
        for language in languages:
            items = [SoldUniversalSmall.from_orm_model(item, language) for item in sold_items]
            await self.sold_cache_repo.set_by_owner(owner_id, language, items, ttl)

    async def fill_sold_universal_by_universal_id(self, sold_universal_id: int) -> None:
        sold_item = await self.sold_repo.get_by_id_with_relations(sold_universal_id)
        if not sold_item:
            await self.sold_single_cache_repo.delete_by_id(sold_universal_id)
            return

        languages = self._extract_languages([sold_item])
        if not languages:
            await self.sold_single_cache_repo.delete_by_id(sold_universal_id)
            return

        ttl = int(self.conf.redis_time_storage.sold_universal_product_by_product.total_seconds())
        for language in languages:
            dto = SoldUniversalFull.from_orm_model(sold_item, language=language)
            await self.sold_single_cache_repo.set(dto, language, ttl)

    @staticmethod
    def _extract_languages(items: Iterable[SoldUniversal]) -> set[str]:
        return {
            translate.language
            for item in items
            for translate in item.storage.translations
            if translate.language
        }
