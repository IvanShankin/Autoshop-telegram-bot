from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload

from src.database.models.categories import Categories, ProductAccounts, AccountStorage, UniversalStorage, \
    ProductUniversal, StorageStatus
from src.models.read_models import CategoriesDTO
from src.repository.database.base import DatabaseBase


class CategoriesRepository(DatabaseBase):

    async def get_by_id(
        self,
        category_id: int,
        *,
        with_translations: bool = False,
        with_ui_image: bool = False,
    ) -> Optional[CategoriesDTO]:
        stmt = select(Categories).where(Categories.category_id == category_id)

        if with_translations:
            stmt = stmt.options(selectinload(Categories.translations))
        if with_ui_image:
            stmt = stmt.options(selectinload(Categories.ui_image))

        result = await self.session_db.execute(stmt)
        category = result.scalar_one_or_none()
        return CategoriesDTO.model_validate(category) if category else None

    async def get_children(
        self,
        parent_id: Optional[int],
        *,
        order_by_index: bool = True,
        with_translations: bool = False,
    ) -> list[CategoriesDTO]:
        stmt = select(Categories).where(Categories.parent_id == parent_id)

        if with_translations:
            stmt = stmt.options(selectinload(Categories.translations))

        if order_by_index:
            stmt = stmt.order_by(Categories.index.asc())

        result = await self.session_db.execute(stmt)
        categories = list(result.scalars().all())
        return [CategoriesDTO.model_validate(category) for category in categories]

    async def get_main_categories(
        self,
        *,
        with_translations: bool = False,
    ) -> list[CategoriesDTO]:
        stmt = select(Categories).where(Categories.is_main == True)

        if with_translations:
            stmt = stmt.options(selectinload(Categories.translations))

        stmt = stmt.order_by(Categories.index.asc())

        result = await self.session_db.execute(stmt)
        categories = list(result.scalars().all())
        return [CategoriesDTO.model_validate(category) for category in categories]

    async def get_max_index_by_parent(self, parent_id: Optional[int]) -> int:
        stmt = select(func.max(Categories.index)).where(Categories.parent_id == parent_id)
        result = await self.session_db.execute(stmt)
        value = result.scalar_one_or_none()
        return int(value) if value is not None else -1

    async def get_quantity_products_in_category(self, category_id: int) -> int:
        stmt = select(
            select(func.count())
            .select_from(ProductAccounts)
            .join(ProductAccounts.account_storage)
            .where(
                (ProductAccounts.category_id == category_id) &
                (AccountStorage.status == StorageStatus.FOR_SALE)
            )
            .scalar_subquery()
            +
            select(func.count())
            .select_from(ProductUniversal)
            .join(ProductUniversal.storage)
            .where(
                (ProductUniversal.category_id == category_id) &
                (UniversalStorage.status == StorageStatus.FOR_SALE)
            )
            .scalar_subquery()

            # ПРИ ДОБАВЛЕНИЕ НОВЫХ ТОВАРОВ, РАСШИРИТЬ ПОИСК
        )

        result = await self.session_db.execute(stmt)
        return result.scalar_one()

    async def count_all(self) -> int:
        result = await self.session_db.execute(select(func.count()).select_from(Categories))
        return int(result.scalar() or 0)

    async def create_category(self, **values) -> CategoriesDTO:
        created = await super().create(Categories, **values)
        return CategoriesDTO.model_validate(created)

    async def update(
        self,
        category_id: int,
        **values: Any,
    ) -> Optional[CategoriesDTO]:
        if not values:
            return await self.get_by_id(category_id)

        stmt = (
            update(Categories)
            .where(Categories.category_id == category_id)
            .values(**values)
            .returning(Categories)
        )
        result = await self.session_db.execute(stmt)
        category = result.scalar_one_or_none()
        return CategoriesDTO.model_validate(category) if category else None

    async def delete(self, category_id: int) -> Optional[CategoriesDTO]:
        stmt = (
            delete(Categories)
            .where(Categories.category_id == category_id)
            .returning(Categories)
        )
        result = await self.session_db.execute(stmt)
        category = result.scalar_one_or_none()
        return CategoriesDTO.model_validate(category) if category else None

    async def shift_indexes_after_insert(
        self,
        *,
        parent_id: Optional[int],
        from_index: int,
    ) -> None:
        stmt = (
            update(Categories)
            .where(Categories.parent_id == parent_id)
            .where(Categories.index >= from_index)
            .values(index=Categories.index + 1)
        )
        await self.session_db.execute(stmt)

    async def shift_indexes_after_delete(
        self,
        *,
        parent_id: Optional[int],
        from_index: int,
    ) -> None:
        stmt = (
            update(Categories)
            .where(Categories.parent_id == parent_id)
            .where(Categories.index > from_index)
            .values(index=Categories.index - 1)
        )
        await self.session_db.execute(stmt)
