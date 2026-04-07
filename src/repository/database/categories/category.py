from __future__ import annotations

from typing import Any, Optional, List, Dict

from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload

from src.database.models.categories import Categories, ProductAccounts, AccountStorage, UniversalStorage, \
    ProductUniversal, StorageStatus
from src.models.read_models import CategoriesDTO
from src.repository.database.base import DatabaseBase


class CategoriesRepository(DatabaseBase):

    async def get_categories_by_ids(
        self,
        categories_ids: List[int],
        *,
        order_by_index: bool = True,
    ) -> List[CategoriesDTO]:
        stmt = select(Categories).where(Categories.category_id.in_(categories_ids))

        if order_by_index:
            stmt = stmt.order_by(Categories.index.asc())

        result = await self.session_db.execute(stmt)
        categories = list(result.scalars().all())
        return [CategoriesDTO.model_validate(category) for category in categories]

    async def get_by_id(
        self,
        category_id: int,
    ) -> Optional[CategoriesDTO]:
        stmt = select(Categories).where(Categories.category_id == category_id)

        result = await self.session_db.execute(stmt)
        category = result.scalar_one_or_none()
        return CategoriesDTO.model_validate(category) if category else None

    async def get_by_id_with_translations(
        self,
        category_id: int
    ) -> Categories | None:
        """
        :return: Категории с подгруженным переводами
        """
        result = await self.session_db.execute(
            select(Categories)
            .where(Categories.category_id == category_id)
            .options(selectinload(Categories.translations))
            .order_by(Categories.index.asc())
        )
        return result.scalar_one_or_none()  # ORM

    async def get_children(
        self,
        parent_id: Optional[int],
        *,
        order_by_index: bool = True,
    ) -> list[CategoriesDTO]:
        stmt = select(Categories).where(Categories.parent_id == parent_id)

        if order_by_index:
            stmt = stmt.order_by(Categories.index.asc())

        result = await self.session_db.execute(stmt)
        categories = list(result.scalars().all())
        return [CategoriesDTO.model_validate(category) for category in categories]

    async def get_children_with_translations(
        self,
        parent_id: Optional[int],
    ) -> List[Categories]:
        """
        :return: Категории с подгруженным переводами
        """
        result = await self.session_db.execute(
            select(Categories)
            .where(Categories.parent_id == parent_id)
            .options(selectinload(Categories.translations))
            .order_by(Categories.index.asc())
        )
        return list(result.scalars().all()) # ORM

    async def get_main_categories(
        self,
    ) -> list[CategoriesDTO]:
        stmt = select(Categories).where(Categories.is_main == True).order_by(Categories.index.asc())
        result = await self.session_db.execute(stmt)
        categories = list(result.scalars().all())
        return [CategoriesDTO.model_validate(category) for category in categories]

    async def get_main_with_translations(self) -> List[Categories]:
        """
        :return: Категории с подгруженным переводами
        """
        result = await self.session_db.execute(
            select(Categories)
            .where(Categories.is_main == True)
            .options(selectinload(Categories.translations))
            .order_by(Categories.index.asc())
        )
        return list(result.scalars().all())  # ORM

    async def get_max_index_by_parent(self, parent_id: Optional[int]) -> int:
        """
        :param parent_id: Если не указывать, то вернёт по главным
        :return:
        """
        stmt = select(func.max(Categories.index)).where(Categories.parent_id == parent_id)
        result = await self.session_db.execute(stmt)
        value = result.scalar_one_or_none()
        return int(value) if value is not None else -1

    async def get_quantity_products_map(self, category_ids: List[int]) -> Dict[int, int]:
        if not category_ids:
            return {}

        stmt_accounts = (
            select(
                ProductAccounts.category_id,
                func.count().label("cnt")
            )
            .join(ProductAccounts.account_storage)
            .where(
                ProductAccounts.category_id.in_(category_ids),
                AccountStorage.status == StorageStatus.FOR_SALE
            )
            .group_by(ProductAccounts.category_id)
        )

        stmt_universal = (
            select(
                ProductUniversal.category_id,
                func.count().label("cnt")
            )
            .join(ProductUniversal.storage)
            .where(
                ProductUniversal.category_id.in_(category_ids),
                UniversalStorage.status == StorageStatus.FOR_SALE
            )
            .group_by(ProductUniversal.category_id)
        )

        result_accounts = await self.session_db.execute(stmt_accounts)
        result_universal = await self.session_db.execute(stmt_universal)

        quantity_map: dict[int, int] = {}

        for category_id, cnt in result_accounts.all():
            quantity_map[category_id] = quantity_map.get(category_id, 0) + cnt

        for category_id, cnt in result_universal.all():
            quantity_map[category_id] = quantity_map.get(category_id, 0) + cnt

        return quantity_map

    async def count_all(self) -> int:
        result = await self.session_db.execute(select(func.count()).select_from(Categories))
        return int(result.scalar() or 0)

    async def get_all_ids(self) -> List[int]:
        result = await self.session_db.execute(select(Categories.category_id))
        return list(result.scalars().all())

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

    async def shift_indexes_in_range(
            self,
            *,
            parent_id: Optional[int],
            start: int,
            end: int,
            delta: int,
    ) -> None:
        stmt = (
            update(Categories)
            .where(Categories.parent_id == parent_id)
            .where(Categories.index >= start)
            .where(Categories.index <= end)
            .values(index=Categories.index + delta)
        )
        await self.session_db.execute(stmt)

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
