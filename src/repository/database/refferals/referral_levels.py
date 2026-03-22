from typing import Optional, Sequence, Tuple

from sqlalchemy import select, update, delete

from src.database.models.referrals import ReferralLevels
from src.repository.database.base import DatabaseBase


class ReferralLevelsRepository(DatabaseBase):

    async def get_all(self) -> Sequence[ReferralLevels]:
        stmt = select(ReferralLevels).order_by(ReferralLevels.level.asc())
        result = await self.session_db.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, ref_lvl_id: int) -> Optional[ReferralLevels]:
        stmt = select(ReferralLevels).where(ReferralLevels.referral_level_id == ref_lvl_id)
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_nearby(
        self,
        ref_lvl_id: int,
    ) -> Tuple[Optional[ReferralLevels], Optional[ReferralLevels], Optional[ReferralLevels]]:
        ref_lvls = await self.get_all()

        previous_lvl = None
        current_lvl = None
        next_lvl = None

        for lvl in ref_lvls:
            if current_lvl is not None:
                next_lvl = lvl
                break

            if lvl.referral_level_id == ref_lvl_id:
                current_lvl = lvl
            else:
                previous_lvl = lvl

        return previous_lvl, current_lvl, next_lvl

    async def create_referral_lvl(self, **values) -> ReferralLevels:
        return await super().create(ReferralLevels, **values)

    async def update_referral_lvl(self, ref_lvl_id: int, **values) -> Optional[ReferralLevels]:
        if not values:
            return await self.get_by_id(ref_lvl_id)

        stmt = (
            update(ReferralLevels)
            .where(ReferralLevels.referral_level_id == ref_lvl_id)
            .values(**values)
            .returning(ReferralLevels)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_referral_lvl(self, ref_lvl_id: int) -> Optional[ReferralLevels]:
        stmt = (
            delete(ReferralLevels)
            .where(ReferralLevels.referral_level_id == ref_lvl_id)
            .returning(ReferralLevels)
        )
        result = await self.session_db.execute(stmt)
        return result.scalar_one_or_none()