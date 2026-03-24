from typing import List

from src.read_models import CategoryFull
from src.repository.redis.base import BaseRedisRepo


class CategoriesCacheRepository(BaseRedisRepo):

    def _key_main_categories(self, language: str) -> str:
        return f"main_categories:{language}"

    def _key_pattern_by_main_categories(self) -> str:
        return f"main_categories:*"

    def _key_categories_by_parent(self, parent_id: int, language: str) -> str:
        return f"categories_by_parent:{parent_id}:{language}"

    def _key_pattern_by_parent(self, parent_id: int) -> str:
        return f"categories_by_parent:{parent_id}:*"

    def _key_category(self, category_id: int, language: str) -> str:
        return f"category:{category_id}:{language}"

    def _key_pattern_by_category(self, category_id: int) -> str:
        return f"category:{category_id}:*"

    # ==== main_categories ====

    async def set_main_categories(self, categories: List[CategoryFull], language: str) -> None:
        await self._set_many(
            self._key_main_categories(language),
            categories
        )

    async def get_main_categories(self, language: str) -> List[CategoryFull]:
        return await self._get_many(
            self._key_main_categories(language),
            CategoryFull
        )

    async def delete_main_categories(self) -> None:
        await self.delete_keys_by_pattern(self._key_pattern_by_main_categories())

    # ==== categories_by_parent ====

    async def set_categories_by_parent(self, categories: List[CategoryFull], parent_id: int, language: str):
        await self._set_many(
            self._key_categories_by_parent(parent_id, language),
            categories
        )

    async def get_categories_by_parent(self, parent_id: int, language: str):
        return await self._get_many(
            self._key_categories_by_parent(parent_id, language),
            CategoryFull
        )

    async def delete_categories_by_parent(self, parent_id: int) -> None:
        await self.delete_keys_by_pattern(self._key_pattern_by_parent(parent_id))

    # ==== category ====

    async def set_category(self, category: CategoryFull, language: str):
        await self._set_one(
            self._key_category(category.category_id, language),
            category
        )

    async def get_category(self, category_id: int, language: str):
        return await self._get_one(
            self._key_category(category_id, language),
            CategoryFull
        )

    async def delete_category(self, category_id: int) -> None:
        await self.delete_keys_by_pattern(self._key_pattern_by_category(category_id))
