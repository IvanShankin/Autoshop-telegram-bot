from typing import Optional

from sqlalchemy import select

from src.database.models.discount import ActivatedPromoCodes
from src.read_models.other import ActivatedPromoCodesDTO
from src.repository.database.base import DatabaseBase


class ActivatedPromoCodeRepository(DatabaseBase):

    async def check_activated(self, promo_code_id: int, user_id: int) -> bool:
        stmt = select(ActivatedPromoCodes).where(
            (ActivatedPromoCodes.promo_code_id == promo_code_id) &
            (ActivatedPromoCodes.user_id == user_id)
        )
        result = await self.session_db.execute(stmt)
        return bool(result.scalars().first())

    async def get_by_id(self, activated_id: int) -> Optional[ActivatedPromoCodesDTO]:
        stmt = select(ActivatedPromoCodes).where(ActivatedPromoCodes.activated_promo_code_id == activated_id)
        result = await self.session_db.execute(stmt)
        activated = result.scalar_one_or_none()
        return ActivatedPromoCodesDTO.model_validate(activated) if activated else None

    async def create_activate(self, **values) -> ActivatedPromoCodesDTO:
        created = await super().create(ActivatedPromoCodes, **values)
        return ActivatedPromoCodesDTO.model_validate(created)
