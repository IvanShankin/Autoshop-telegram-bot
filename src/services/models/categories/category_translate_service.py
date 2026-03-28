from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import AccountCategoryNotFound, TranslationAlreadyExists
from src.exceptions.business import TheOnlyTranslation
from src.models.create_models.category import CreateCategoryTranslate
from src.models.read_models import CategoryTranslationDTO, CategoryFull
from src.models.update_models.category import UpdateCategoryTranslationsDTO
from src.repository.database.categories import CategoryTranslationsRepository, CategoriesRepository
from src.repository.redis import CategoriesCacheRepository
from src.services.models.categories.categories_cache_filler_service import CategoriesCacheFillerService


class TranslationsCategoryService:

    def __init__(
        self,
        category_translations_repo: CategoryTranslationsRepository,
        category_repo: CategoriesRepository,
        category_cache_repo: CategoriesCacheRepository,
        category_filler_service: CategoriesCacheFillerService,
        session_db: AsyncSession,
    ):
        self.category_translations_repo = category_translations_repo
        self.category_repo = category_repo
        self.category_cache_repo = category_cache_repo
        self.category_filler_service = category_filler_service
        self.session_db = session_db

    async def get_all_translations_category(self, category_id: int) -> List[CategoryTranslationDTO]:
        return await self.category_translations_repo.get_all_by_category_id(category_id)

    async def create_translation_in_category(
        self,
        data: CreateCategoryTranslate,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> CategoryFull:
        """
        :exception AccountCategoryNotFound: Если category_id не найден.
        :exception TranslationAlreadyExists: Если перевод по данному языку есть.
        """
        category = await self.category_repo.get_by_id_with_translations(data.category_id)
        if not category:
            raise AccountCategoryNotFound()

        if await self.category_translations_repo.exists(data.category_id, data.language):
            raise TranslationAlreadyExists()


        trans = await self.category_translations_repo.create_translate(**(data.model_dump()))

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.category_filler_service.fill_need_category(trans.category_id)

        quantity_map = await self.category_repo.get_quantity_products_map([category.category_id])

        return CategoryFull.from_orm_with_translation(
            category=category,
            quantity_product=quantity_map.get(category.category_id, 0),
            lang=data.language
        )

    async def update_category_translation(
        self,
        data: UpdateCategoryTranslationsDTO,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ) -> CategoryTranslationDTO:
        values = data.model_dump(exclude_unset=True)
        trans = await self.category_translations_repo.update(**values)

        if make_commit:
            await self.session_db.commit()

        if filling_redis and trans:
            await self.category_filler_service.fill_need_category(trans.category_id)

        return trans

    async def delete_all_category_translation(
        self,
        category_id: int,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ):
        await self.category_translations_repo.delete(category_id)
        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.category_filler_service.fill_need_category(category_id)

    async def delete_category_translation(
        self,
        category_id: int,
        language: str,
        make_commit: Optional[bool] = False,
        filling_redis: Optional[bool] = False,
    ):
        """
        :exception AccountCategoryNotFound: Не найдена категория
        :exception TheOnlyTranslation: Если у данной категории это единственный перевод
        """
        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise AccountCategoryNotFound()

        quantity_trans = await self.category_translations_repo.count_by_category_id(category_id)
        if quantity_trans == 1:
            raise TheOnlyTranslation()

        trans = await self.category_translations_repo.delete(category_id, language)

        if make_commit:
            await self.session_db.commit()

        if filling_redis and trans:
            await self.category_filler_service.fill_need_category(category_id)


