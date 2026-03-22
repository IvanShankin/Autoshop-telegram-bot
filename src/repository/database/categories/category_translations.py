from __future__ import annotations

from typing import List, Optional, Any

from sqlalchemy import select, update, delete, distinct

from src.database.models.categories import CategoryTranslation
from src.repository.database.base import DatabaseBase


class CategoryTranslationsRepository(DatabaseBase):

    # -------------------------
    # Queries
    # -------------------------

    async def get_all_by_category_id(
        self,
        category_id: int,
    ) -> List[CategoryTranslation]:
        result = await self.session_db.execute(
            select(CategoryTranslation)
            .where(CategoryTranslation.category_id == category_id)
        )
        return list(result.scalars().all())

    async def get_by_category_and_lang(
        self,
        category_id: int,
        language: str,
    ) -> Optional[CategoryTranslation]:
        result = await self.session_db.execute(
            select(CategoryTranslation).where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
        )
        return result.scalar_one_or_none()

    async def get_languages_by_category_id(
        self,
        category_id: int,
    ) -> List[str]:
        result = await self.session_db.execute(
            select(distinct(CategoryTranslation.lang))
            .where(CategoryTranslation.category_id == category_id)
        )
        return list(result.scalars().all())

    async def exists(
        self,
        category_id: int,
        language: str,
    ) -> bool:
        result = await self.session_db.execute(
            select(CategoryTranslation.category_id).where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
        )
        return result.scalar_one_or_none() is not None

    # -------------------------
    # Commands
    # -------------------------
    async def create_translate(self, **values) -> CategoryTranslation:
        return await super().create(CategoryTranslation, **values)

    async def update(
        self,
        category_id: int,
        language: str,
        **values: Any,
    ) -> Optional[CategoryTranslation]:

        if not values:
            return await self.get_by_category_and_lang(category_id, language)

        result = await self.session_db.execute(
            update(CategoryTranslation)
            .where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
            .values(**values)
            .returning(CategoryTranslation)
        )

        return result.scalar_one_or_none()

    async def delete(
        self,
        category_id: int,
        language: str,
    ) -> None:
        await self.session_db.execute(
            delete(CategoryTranslation).where(
                (CategoryTranslation.category_id == category_id) &
                (CategoryTranslation.lang == language)
            )
        )

    async def count_by_category_id(self, category_id: int) -> int:
        result = await self.session_db.execute(
            select(CategoryTranslation.category_id)
            .where(CategoryTranslation.category_id == category_id)
        )
        return len(result.scalars().all())