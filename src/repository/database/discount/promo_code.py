from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, func, update, and_

from src.database.models.discount import PromoCodes
from src.repository.database.base import DatabaseBase


class PromoCodeRepository(DatabaseBase):

    async def get_by_id(self, promo_code_id: int) -> Optional[PromoCodes]:
        stmt = select(PromoCodes).where(PromoCodes.promo_code_id == promo_code_id)
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str, only_valid: bool = True) -> Optional[PromoCodes]:
        stmt = select(PromoCodes).where(PromoCodes.activation_code == code)
        if only_valid:
            stmt = stmt.where(PromoCodes.is_valid == True)
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_page(
        self,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        show_not_valid: bool = False
    ) -> List[PromoCodes]:
        stmt = select(PromoCodes)
        if not show_not_valid:
            stmt = stmt.where(PromoCodes.is_valid == True)

        if page is not None and page_size is not None:
            stmt = stmt.limit(page_size).offset((page - 1) * page_size)

        result = await self.session_db.execute(stmt.order_by(PromoCodes.start_at.desc()))
        return result.scalars().all()

    async def set_not_valid_promo_codes(self, data_time_to: datetime) -> List[PromoCodes]:
        """
        Установит is_valid=False у промокодов где дата меньше чем `data_time_to`
        :return:
        """
        result_db = await self.session_db.execute(
            update(PromoCodes)
            .where(
                and_(
                    PromoCodes.is_valid.is_(True),
                    PromoCodes.expire_at <= data_time_to
                )
            )
            .values(is_valid=False)
            .returning(PromoCodes)
        )
        return result_db.scalars().all()

    async def count(self, consider_invalid: bool = False) -> int:
        stmt = select(func.count()).select_from(PromoCodes)
        if not consider_invalid:
            stmt = stmt.where(PromoCodes.is_valid == True)
        result = await self.session_db.execute(stmt)
        return int(result.scalar() or 0)

    async def create_promo_code(self, **values) -> PromoCodes:
        return await super().create(PromoCodes, **values)

    async def deactivate(self, promo_code_id: int) -> Optional[PromoCodes]:
        stmt = (
            update(PromoCodes)
            .where(PromoCodes.promo_code_id == promo_code_id)
            .values(is_valid=False)
            .returning(PromoCodes)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_activation(
        self,
        promo_code_id: int,
        current_counter: int
    ) -> int:
        result = await self.session_db.execute(
            update(PromoCodes)
            .where(PromoCodes.promo_code_id == promo_code_id)
            .values(activated_counter=current_counter + 1)
            .returning(PromoCodes.activated_counter)
        )
        new_value = result.scalar_one()
        return new_value