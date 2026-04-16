from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, func, update, and_

from src.database.models.discount import PromoCodes
from src.models.read_models.other import PromoCodesDTO
from src.repository.database.base import DatabaseBase


class PromoCodeRepository(DatabaseBase):

    async def get_by_id(
        self,
        promo_code_id: int,
        *,
        only_valid: bool = True,
    ) -> Optional[PromoCodesDTO]:
        stmt = select(PromoCodes).where(PromoCodes.promo_code_id == promo_code_id)
        if only_valid:
            stmt = stmt.where(PromoCodes.is_valid == True)
        result = await self.session_db.execute(stmt)
        promo = result.scalar_one_or_none()
        return PromoCodesDTO.model_validate(promo) if promo else None

    async def get_by_code(self, code: str, only_valid: bool = True) -> Optional[PromoCodesDTO]:
        stmt = select(PromoCodes).where(PromoCodes.activation_code == code)
        if only_valid:
            stmt = stmt.where(PromoCodes.is_valid == True)
        result = await self.session_db.execute(stmt)
        promo = result.scalar_one_or_none()
        return PromoCodesDTO.model_validate(promo) if promo else None

    async def get_page(
        self,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        show_not_valid: bool = False
    ) -> List[PromoCodesDTO]:
        stmt = select(PromoCodes)
        if not show_not_valid:
            stmt = stmt.where(PromoCodes.is_valid == True)

        if page is not None and page_size is not None:
            stmt = stmt.limit(page_size).offset((page - 1) * page_size)

        result = await self.session_db.execute(stmt.order_by(PromoCodes.start_at.desc()))
        promos = list(result.scalars().all())
        return [PromoCodesDTO.model_validate(promo) for promo in promos]

    async def get_not_valid_promo_codes(self, data_time_to: datetime) -> List[PromoCodesDTO]:
        """
        :return: Промокоды где дата меньше чем `data_time_to`
        """
        result_db = await self.session_db.execute(
            select(PromoCodes)
            .where(
                and_(
                    PromoCodes.is_valid.is_(True),
                    PromoCodes.expire_at <= data_time_to
                )
            )
        )
        promos = list(result_db.scalars().all())
        return [PromoCodesDTO.model_validate(promo) for promo in promos]

    async def count(self, consider_invalid: bool = False) -> int:
        stmt = select(func.count()).select_from(PromoCodes)
        if not consider_invalid:
            stmt = stmt.where(PromoCodes.is_valid == True)
        result = await self.session_db.execute(stmt)
        return int(result.scalar() or 0)

    async def create_promo_code(self, **values) -> PromoCodesDTO:
        created = await super().create(PromoCodes, **values)
        return PromoCodesDTO.model_validate(created)

    async def deactivate(self, promo_code_id: int) -> Optional[PromoCodesDTO]:
        stmt = (
            update(PromoCodes)
            .where(PromoCodes.promo_code_id == promo_code_id)
            .values(is_valid=False)
            .returning(PromoCodes)
        )
        result = await self.session_db.execute(stmt)
        promo = result.scalar_one_or_none()
        return PromoCodesDTO.model_validate(promo) if promo else None

    async def increment_activation(
        self,
        promo_code_id: int,
        current_counter: int
    ) -> int:
        """
        :return: Новое число активаций
        """
        result = await self.session_db.execute(
            update(PromoCodes)
            .where(PromoCodes.promo_code_id == promo_code_id)
            .values(activated_counter=current_counter + 1)
            .returning(PromoCodes.activated_counter)
        )
        new_value = result.scalar_one()
        return new_value
