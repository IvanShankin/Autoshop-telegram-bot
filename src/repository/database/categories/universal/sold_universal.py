from typing import Optional, List

from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from src.database.models.categories import SoldUniversal, UniversalStorage
from src.models.read_models import SoldUniversalDTO
from src.repository.database.base import DatabaseBase


class SoldUniversalRepository(DatabaseBase):

    async def get_by_id(self, sold_id: int) -> Optional[SoldUniversalDTO]:
        result = await self.session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_id)
        )
        sold = result.scalar_one_or_none()
        return SoldUniversalDTO.model_validate(sold) if sold else None

    async def get_by_id_with_relations(
        self,
        sold_id: int,
        *,
        active_only: bool = True,
    ) -> Optional[SoldUniversal]:
        stmt = (
            select(SoldUniversal)
            .options(
                selectinload(SoldUniversal.storage)
                .selectinload(UniversalStorage.translations)
            )
            .where(SoldUniversal.sold_universal_id == sold_id)
        )
        if active_only:
            stmt = stmt.where(SoldUniversal.storage.has(is_active=True))

        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_owner(self, owner_id: int) -> List[SoldUniversalDTO]:
        result = await self.session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.owner_id == owner_id)
        )
        sold_items = list(result.scalars().all())
        return [SoldUniversalDTO.model_validate(item) for item in sold_items]

    async def get_by_owner_with_relations(
        self,
        owner_id: int,
        *,
        active_only: bool = True,
        order_desc: bool = True,
    ) -> List[SoldUniversal]:
        stmt = (
            select(SoldUniversal)
            .options(
                selectinload(SoldUniversal.storage)
                .selectinload(UniversalStorage.translations)
            )
            .where(SoldUniversal.owner_id == owner_id)
        )
        if active_only:
            stmt = stmt.where(SoldUniversal.storage.has(is_active=True))
        if order_desc:
            stmt = stmt.order_by(SoldUniversal.sold_at.desc())

        result = await self.session_db.execute(stmt)
        return list(result.scalars().all())

    async def get_page_by_owner(
        self,
        owner_id: int,
        *,
        page: int,
        page_size: int,
        active_only: bool = True,
    ) -> List[SoldUniversal]:
        stmt = (
            select(SoldUniversal)
            .options(
                selectinload(SoldUniversal.storage)
                .selectinload(UniversalStorage.translations)
            )
            .where(SoldUniversal.owner_id == owner_id)
            .order_by(SoldUniversal.sold_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        if active_only:
            stmt = stmt.where(SoldUniversal.storage.has(is_active=True))

        result = await self.session_db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_owner(self, owner_id: int, *, active_only: bool = True) -> int:
        stmt = select(func.count(SoldUniversal.sold_universal_id)).where(
            SoldUniversal.owner_id == owner_id
        )
        if active_only:
            stmt = stmt.where(SoldUniversal.storage.has(is_active=True))

        result = await self.session_db.execute(stmt)
        return int(result.scalar() or 0)

    async def get_by_storage_id(self, universal_storage_id: int) -> Optional[SoldUniversalDTO]:
        result = await self.session_db.execute(
            select(SoldUniversal)
            .where(SoldUniversal.universal_storage_id == universal_storage_id)
        )
        sold = result.scalar_one_or_none()
        return SoldUniversalDTO.model_validate(sold) if sold else None

    async def create_sold(self, **values) -> SoldUniversalDTO:
        created = await super().create(SoldUniversal, **values)
        return SoldUniversalDTO.model_validate(created)

    async def delete(self, sold_id: int) -> None:
        await self.session_db.execute(
            delete(SoldUniversal)
            .where(SoldUniversal.sold_universal_id == sold_id)
        )
