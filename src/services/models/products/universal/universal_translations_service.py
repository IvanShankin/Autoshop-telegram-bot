from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import TranslationAlreadyExists
from src.exceptions.domain import UniversalStorageNotFound
from src.models.create_models.universal import CreateUniversalTranslationDTO
from src.models.read_models import UniversalStoragePydantic, UniversalStorageTranslationDTO
from src.models.update_models.universal import UpdateUniversalTranslationDTO
from src.repository.database.categories.universal import (
    UniversalStorageRepository,
    UniversalTranslationRepository,
)
from src.services.models.products.universal.universal_cache_filler_service import UniversalCacheFillerService


class UniversalTranslationsService:

    def __init__(
        self,
        storage_repo: UniversalStorageRepository,
        translation_repo: UniversalTranslationRepository,
        cache_filler: UniversalCacheFillerService,
        session_db: AsyncSession,
    ):
        self.storage_repo = storage_repo
        self.translation_repo = translation_repo
        self.cache_filler = cache_filler
        self.session_db = session_db

    async def get_all_translations(
        self,
        universal_storage_id: int,
    ) -> List[UniversalStorageTranslationDTO]:
        return await self.translation_repo.get_all(universal_storage_id)

    async def create_translation(
        self,
        data: CreateUniversalTranslationDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> UniversalStoragePydantic:
        """
        :exception UniversalStorageNotFound: Хранилище не найдено.
        :exception TranslationAlreadyExists: Перевод по данному языку уже существует.
        """
        storage = await self.storage_repo.get_orm_by_id(
            data.universal_storage_id,
            with_relations=True,
        )
        if not storage:
            raise UniversalStorageNotFound(
                f"UniversalStorage с ID = {data.universal_storage_id} не найден"
            )

        if await self.translation_repo.exists(data.universal_storage_id, data.language):
            raise TranslationAlreadyExists(
                f"Перевод по языку '{data.language}' уже существует"
            )

        await self.translation_repo.create_translate(**data.model_dump(exclude_unset=True))

        if make_commit:
            await self.session_db.commit()

        storage = await self.storage_repo.get_orm_by_id(
            data.universal_storage_id,
            with_relations=True,
        )

        if filling_redis:
            for product in storage.product:
                await self.cache_filler.fill_product_universal_by_category_id(product.category_id)
                await self.cache_filler.fill_product_universal_by_product_id(product.product_universal_id)

            for sold in storage.sold_universal:
                await self.cache_filler.fill_sold_universal_by_owner_id(sold.owner_id)
                await self.cache_filler.fill_sold_universal_by_universal_id(sold.sold_universal_id)

        return UniversalStoragePydantic.from_orm_model(storage, data.language)

    async def update_translation(
        self,
        data: UpdateUniversalTranslationDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> UniversalStorageTranslationDTO | None:
        values = data.model_dump(exclude_unset=True)
        translation = await self.translation_repo.update(**values)

        if make_commit:
            await self.session_db.commit()

        if translation and filling_redis:
            storage = await self.storage_repo.get_orm_by_id(
                data.universal_storage_id,
                with_relations=True,
            )
            if storage:
                for product in storage.product:
                    await self.cache_filler.fill_product_universal_by_category_id(product.category_id)
                    await self.cache_filler.fill_product_universal_by_product_id(product.product_universal_id)

                for sold in storage.sold_universal:
                    await self.cache_filler.fill_sold_universal_by_owner_id(sold.owner_id)
                    await self.cache_filler.fill_sold_universal_by_universal_id(sold.sold_universal_id)

        return translation
