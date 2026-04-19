from typing import Optional, Sequence, Tuple

from sqlalchemy import select, update, delete

from src.database.models.referrals import ReferralLevels
from src.models.read_models.other import ReferralLevelsDTO
from src.repository.database.base import DatabaseBase


class ReferralLevelsRepository(DatabaseBase):

    async def get_all(self) -> Sequence[ReferralLevelsDTO]:
        stmt = select(ReferralLevels).order_by(ReferralLevels.level.asc())
        result = await self.session_db.execute(stmt)
        levels = list(result.scalars().all())
        return [ReferralLevelsDTO.model_validate(level) for level in levels]

    async def get_by_id(self, ref_lvl_id: int) -> Optional[ReferralLevelsDTO]:
        stmt = select(ReferralLevels).where(ReferralLevels.referral_level_id == ref_lvl_id)
        result = await self.session_db.execute(stmt)
        level = result.scalar_one_or_none()
        return ReferralLevelsDTO.model_validate(level) if level else None

    async def get_nearby(
        self,
        ref_lvl_id: int,
    ) -> Tuple[Optional[ReferralLevelsDTO], Optional[ReferralLevelsDTO], Optional[ReferralLevelsDTO]]:
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

    async def create_referral_lvl(self, **values) -> ReferralLevelsDTO:
        created = await super().create(ReferralLevels, **values)
        return ReferralLevelsDTO.model_validate(created)

    async def update_referral_lvl(self, ref_lvl_id: int, **values) -> Optional[ReferralLevelsDTO]:
        if not values:
            return await self.get_by_id(ref_lvl_id)

        stmt = (
            update(ReferralLevels)
            .where(ReferralLevels.referral_level_id == ref_lvl_id)
            .values(**values)
            .returning(ReferralLevels)
        )
        result = await self.session_db.execute(stmt)
        level = result.scalar_one_or_none()
        return ReferralLevelsDTO.model_validate(level) if level else None

    async def update_referral_lvl_after_removal(self, ref_lvl_remote: int) -> Optional[ReferralLevelsDTO]:
        stmt = (
            update(ReferralLevels)
            .where(ReferralLevels.level > ref_lvl_remote)
            .values(level=ReferralLevels.level - 1)
            .returning(ReferralLevels)
        )
        result = await self.session_db.execute(stmt)
        level = result.scalar_one_or_none()
        return ReferralLevelsDTO.model_validate(level) if level else None

    async def delete_referral_lvl(self, ref_lvl_id: int) -> Optional[ReferralLevelsDTO]:
        stmt = (
            delete(ReferralLevels)
            .where(ReferralLevels.referral_level_id == ref_lvl_id)
            .returning(ReferralLevels)
        )
        result = await self.session_db.execute(stmt)
        level = result.scalar_one_or_none()
        return ReferralLevelsDTO.model_validate(level) if level else None
