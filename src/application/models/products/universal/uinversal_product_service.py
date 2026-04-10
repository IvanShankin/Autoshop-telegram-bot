import shutil
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.exceptions.domain import CategoryNotFound, UniversalProductNotFound, UniversalStorageNotFound
from src.models.create_models.universal import CreateProductUniversalDTO
from src.models.read_models import ProductUniversalFull, ProductUniversalSmall, ProductUniversalDTO
from src.repository.database.categories import CategoriesRepository
from src.repository.database.categories.universal import (
    ProductUniversalRepository,
    UniversalStorageRepository,
)
from src.repository.redis.product_universal import (
    ProductUniversalCacheRepository,
    ProductUniversalSingleCacheRepository,
)
from src.infrastructure.files._media_paths import create_path_universal_storage
from src.application.models.categories.categories_cache_filler_service import CategoriesCacheFillerService
from src.application.models.products.universal.universal_cache_filler_service import UniversalCacheFillerService


class UniversalProductService:

    def __init__(
        self,
        product_repo: ProductUniversalRepository,
        storage_repo: UniversalStorageRepository,
        category_repo: CategoriesRepository,
        product_cache_repo: ProductUniversalCacheRepository,
        product_single_cache_repo: ProductUniversalSingleCacheRepository,
        cache_filler: UniversalCacheFillerService,
        category_filler: CategoriesCacheFillerService,
        conf: Config,
        session_db: AsyncSession,
    ):
        self.product_repo = product_repo
        self.storage_repo = storage_repo
        self.category_repo = category_repo
        self.product_cache_repo = product_cache_repo
        self.product_single_cache_repo = product_single_cache_repo
        self.cache_filler = cache_filler
        self.category_filler = category_filler
        self.conf = conf
        self.session_db = session_db

    async def get_product_universal_by_category_id(
        self,
        category_id: int,
        *,
        get_full: bool = False,
        language: str | None = None,
    ) -> List[ProductUniversalSmall | ProductUniversalFull]:
        """
        Возвращает только товары со статусом for_sale.
        """
        if get_full:
            if language is None:
                language = self.conf.app.default_lang
            return await self.product_repo.get_full_by_category(
                category_id,
                language=language,
                only_for_sale=True,
            )

        cached = await self.product_cache_repo.get_by_category(category_id)
        if cached:
            return cached

        products = await self.product_repo.get_by_category_for_sale(category_id)
        items = [ProductUniversalSmall(**p.model_dump()) for p in products]
        if items:
            await self.product_cache_repo.set_by_category(category_id, items)
        return items

    async def get_product_universal_by_product_id(
        self,
        product_universal_id: int,
        language: str | None = None,
    ) -> ProductUniversalFull | None:
        cached = await self.product_single_cache_repo.get(product_universal_id)
        if cached:
            return cached

        if language is None:
            language = self.conf.app.default_lang

        product = await self.product_repo.get_full_by_id(
            product_universal_id,
            language=language,
        )
        if product:
            await self.cache_filler.fill_product_universal_by_product_id(product_universal_id)
        return product

    async def create_product_universal(
        self,
        data: CreateProductUniversalDTO,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> ProductUniversalDTO:
        """
        :exception UniversalStorageNotFound: Хранилище не найдено.
        :exception CategoryNotFound: Категория не найдена.
        """
        storage = await self.storage_repo.get_by_id(data.universal_storage_id)
        if not storage:
            raise UniversalStorageNotFound()

        category = await self.category_repo.get_by_id(data.category_id)
        if not category:
            raise CategoryNotFound()

        product = await self.product_repo.create_product(**data.model_dump(exclude_unset=True))

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_filler.fill_product_universal_by_product_id(product.product_universal_id)
            await self.cache_filler.fill_product_universal_by_category_id(product.category_id)
            await self.category_filler.fill_need_category(categories=[category])

        return product

    async def delete_product_universal(
        self,
        product_universal_id: int,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> None:
        """
        :exception UniversalProductNotFound: Товар не найден.
        """
        product = await self.product_repo.get_by_id(product_universal_id)
        if not product:
            raise UniversalProductNotFound(
                f"Продукт с id = {product_universal_id} не найден"
            )

        await self.product_repo.delete(product_universal_id)

        if make_commit:
            await self.session_db.commit()

        if filling_redis:
            await self.cache_filler.fill_product_universal_by_category_id(product.category_id)
            await self.cache_filler.fill_product_universal_by_product_id(product_universal_id)
            await self.category_filler.fill_need_category(product.category_id)

    async def delete_product_universal_by_category(
        self,
        category_id: int,
        make_commit: bool = True,
        filling_redis: bool = True,
    ) -> None:
        """
        Удаляет товары из БД и с диска (если есть файл).
        """
        product_ids = await self.product_repo.get_ids_by_category(category_id)
        storage_ids = await self.product_repo.get_storage_ids_by_category(category_id)

        deleted_storages = await self.storage_repo.delete_by_ids(storage_ids)

        if make_commit:
            await self.session_db.commit()

        for storage in deleted_storages:
            if not storage.original_filename:
                continue

            folder = create_path_universal_storage(
                status=storage.status,
                uuid=storage.storage_uuid,
                return_path_obj=True
            )
            shutil.rmtree(folder.parent, ignore_errors=True)

        if filling_redis and deleted_storages:
            await self.category_filler.fill_need_category(category_id)
            await self.cache_filler.fill_product_universal_by_category_id(category_id)
            for prod_id in product_ids:
                await self.cache_filler.fill_product_universal_by_product_id(prod_id)
