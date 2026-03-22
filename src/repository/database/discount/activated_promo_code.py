from typing import Optional

from sqlalchemy import select

from src.database.models.discount import ActivatedPromoCodes
from src.repository.database.base import DatabaseBase


class ActivatedPromoCodeRepository(DatabaseBase):

    async def check_activated(self, promo_code_id: int, user_id: int) -> bool:
        stmt = select(ActivatedPromoCodes).where(
            (ActivatedPromoCodes.promo_code_id == promo_code_id) &
            (ActivatedPromoCodes.user_id == user_id)
        )
        result = await self.session_db.execute(stmt)
        return bool(result.scalars().first())

    async def get_by_id(self, activated_id: int) -> Optional[ActivatedPromoCodes]:
        stmt = select(ActivatedPromoCodes).where(ActivatedPromoCodes.activated_promo_code_id == activated_id)
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_activate(self, **values) -> ActivatedPromoCodes:
        return await super().create(ActivatedPromoCodes, **values)