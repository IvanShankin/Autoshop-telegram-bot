from typing import Optional, Sequence

from sqlalchemy import select, update

from src.database.models.referrals import Referrals
from src.models.read_models.other import ReferralsDTO
from src.repository.database.base import DatabaseBase


class ReferralsRepository(DatabaseBase):

    async def get_all_by_owner(self, user_id: int) -> Sequence[ReferralsDTO]:
        stmt = (
            select(Referrals)
            .where(Referrals.owner_user_id == user_id)
            .order_by(Referrals.created_at.desc())
        )
        result = await self.session_db.execute(stmt)
        referrals = list(result.scalars().all())
        return [ReferralsDTO.model_validate(ref) for ref in referrals]

    async def get_by_referral_id(self, referral_id: int) -> Optional[ReferralsDTO]:
        stmt = select(Referrals).where(Referrals.referral_id == referral_id)
        result = await self.session_db.execute(stmt)
        referral = result.scalar_one_or_none()
        return ReferralsDTO.model_validate(referral) if referral else None

    async def create_referral(self, **values) -> ReferralsDTO:
        created = await super().create(Referrals, **values)
        return ReferralsDTO.model_validate(created)

    async def update_level(self, referral_id: int, level: int) -> Optional[ReferralsDTO]:
        stmt = (
            update(Referrals)
            .where(Referrals.referral_id == referral_id)
            .values(level=level)
            .returning(Referrals)
        )
        result = await self.session_db.execute(stmt)
        referral = result.scalar_one_or_none()
        return ReferralsDTO.model_validate(referral) if referral else None
