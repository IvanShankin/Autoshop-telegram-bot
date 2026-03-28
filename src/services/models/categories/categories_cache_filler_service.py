from typing import List, Optional

from src.database.models.categories import Categories
from src.models.read_models import CategoryFull, CategoriesDTO
from src.repository.database.categories import CategoriesRepository
from src.repository.redis import CategoriesCacheRepository


class CategoriesCacheFillerService:

    def __init__(
        self,
        category_repo: CategoriesRepository,
        category_cache_repo: CategoriesCacheRepository,
    ):
        self.category_repo = category_repo
        self.cache_repo = category_cache_repo

    async def _build_category_full_list(
            self,
            categories: list[Categories]
    ) -> dict[str, list[CategoryFull]]:
        if not categories:
            return {}

        categories = sorted(categories, key=lambda x: x.index or 0)

        category_ids = [c.category_id for c in categories]
        quantity_map = await self.category_repo.get_quantity_products_map(category_ids)

        langs = {
            t.lang
            for c in categories
            for t in c.translations
        }

        result: dict[str, list[CategoryFull]] = {}

        for lang in langs:
            lang_list = []

            for category in categories:
                if not any(t.lang == lang for t in category.translations):
                    continue

                dto = CategoryFull.from_orm_with_translation(
                    category=category,
                    quantity_product=quantity_map.get(category.category_id, 0),
                    lang=lang
                )

                lang_list.append(dto)

            if lang_list:
                result[lang] = lang_list

        return result

    async def fill_main_categories(self) -> None:
        categories = await self.category_repo.get_main_with_translations()
        data = await self._build_category_full_list(categories)

        for lang, items in data.items():
            await self.cache_repo.set_main_categories(items, lang)

    async def fill_category_by_parent(self, parent_id: int) -> None:
        categories = await self.category_repo.get_children_with_translations(parent_id)
        data = await self._build_category_full_list(categories)

        for lang, items in data.items():
            await self.cache_repo.set_categories_by_parent(items, parent_id, lang)

    async def fill_category_by_id(self, category_id: int) -> None:
        category = await self.category_repo.get_by_id_with_translations(category_id)
        if not category:
            return

        quantity_map = await self.category_repo.get_quantity_products_map([category.category_id])

        for t in category.translations:
            dto = CategoryFull.from_orm_with_translation(
                category=category,
                quantity_product=quantity_map.get(category.category_id, 0),
                lang=t.lang
            )

            await self.cache_repo.set_category(dto, t.lang)

    async def fill_need_category(
        self,
        categories_ids: Optional[List[int] | int] = None,
        categories: Optional[List[CategoryFull | CategoriesDTO | Categories]] = None,
    ) -> None:
        """
        Заполнит все необходимые разделы для категорий. Необходимо передать хотя бы один аргумент
        """

        if not categories_ids and not categories:
            raise ValueError("Необходимо передать хотя бы один аргумент")

        if isinstance(categories_ids, int):
            categories_ids = [categories_ids]

        if not categories:
            categories = await self.category_repo.get_categories_by_ids(categories_ids)

        there_is_mains = False
        all_parent_ids = []
        all_cat_ids = []

        for cat in categories:
            if cat.is_main:
                there_is_mains = True

            if cat.parent_id:
                all_parent_ids.append(cat.parent_id)

            all_cat_ids.append(cat.category_id)

        all_parent_ids = set(all_parent_ids)

        if there_is_mains:
            await self.fill_main_categories()

        for parent_id in all_parent_ids:
            await self.fill_category_by_parent(parent_id)

        for cat_id in all_cat_ids:
            await self.fill_category_by_id(cat_id)
