from typing import List, Optional

from src.models.read_models import ProductUniversalSmall, ProductUniversalFull, SoldUniversalSmall, SoldUniversalFull
from src.repository.redis.base import BaseRedisRepo


class ProductUniversalCacheRepository(BaseRedisRepo):

    def _key_by_category(self, category_id: int) -> str:
        return f"product_universal_by_category:{category_id}"

    def _pattern_all(self) -> str:
        return "product_universal_by_category:*"

    async def set_by_category(
        self,
        category_id: int,
        products: List[ProductUniversalSmall]
    ) -> None:
        await self._set_many(
            self._key_by_category(category_id),
            products
        )

    async def get_by_category(
        self,
        category_id: int
    ) -> List[ProductUniversalSmall]:
        return await self._get_many(
            self._key_by_category(category_id),
            ProductUniversalSmall
        )

    async def delete_by_category(self, category_id: int) -> None:
        await self.redis_session.delete(self._key_by_category(category_id))

    async def delete_all(self) -> None:
        await self.delete_keys_by_pattern(self._pattern_all())


class ProductUniversalSingleCacheRepository(BaseRedisRepo):

    def _key(self, product_universal_id: int) -> str:
        return f"product_universal:{product_universal_id}"

    def _pattern(self, product_universal_id: int) -> str:
        return f"product_universal:{product_universal_id}*"

    async def set(self, product: ProductUniversalFull) -> None:
        await self._set_one(
            self._key(product.product_universal_id),
            product
        )

    async def get(
        self,
        product_universal_id: int
    ) -> Optional[ProductUniversalFull]:
        return await self._get_one(
            self._key(product_universal_id),
            ProductUniversalFull
        )

    async def delete_by_product_id(self, product_universal_id: int) -> None:
        await self.delete_keys_by_pattern(self._pattern(product_universal_id))


class SoldUniversalCacheRepository(BaseRedisRepo):

    def _key_by_owner(self, owner_id: int, language: str) -> str:
        return f"sold_universal_by_owner_id:{owner_id}:{language}"

    def _pattern_by_owner(self, owner_id: int) -> str:
        return f"sold_universal_by_owner_id:{owner_id}:*"

    async def set_by_owner(
        self,
        owner_id: int,
        language: str,
        items: List[SoldUniversalSmall],
        ttl: int
    ) -> None:
        await self._set_many(
            self._key_by_owner(owner_id, language),
            items,
            ttl=ttl
        )

    async def get_by_owner(
        self,
        owner_id: int,
        language: str
    ) -> List[SoldUniversalSmall]:
        return await self._get_many(
            self._key_by_owner(owner_id, language),
            SoldUniversalSmall
        )

    async def delete_by_owner(self, owner_id: int) -> None:
        await self.delete_keys_by_pattern(self._pattern_by_owner(owner_id))


class SoldUniversalSingleCacheRepository(BaseRedisRepo):

    def _key(self, sold_universal_id: int, language: str) -> str:
        return f"sold_universal:{sold_universal_id}:{language}"

    def _pattern(self, sold_universal_id: int) -> str:
        return f"sold_universal:{sold_universal_id}:*"

    async def set(
        self,
        item: SoldUniversalFull,
        language: str,
        ttl: int
    ) -> None:
        await self._set_one(
            self._key(item.sold_universal_id, language),
            item,
            ttl=ttl
        )

    async def get(
        self,
        sold_universal_id: int,
        language: str
    ) -> Optional[SoldUniversalFull]:
        return await self._get_one(
            self._key(sold_universal_id, language),
            SoldUniversalFull
        )

    async def delete_by_id(self, sold_universal_id: int) -> None:
        await self.delete_keys_by_pattern(self._pattern(sold_universal_id))